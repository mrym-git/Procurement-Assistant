import contextvars
import json
import math
import os
from datetime import datetime
from typing import Any

from bson import ObjectId
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pymongo import MongoClient

from query_explainer import explain_query
from query_validator import validate_pipeline
from scope_detector import is_out_of_scope, out_of_scope_reply
from session_memory import memory

# Context variable that carries the current session_id into tool scope
# without changing the tool function signature.
_current_session_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "session_id", default=""
)

load_dotenv()

# ── MongoDB connection ────────────────────────────────────────────────────────
_client     = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017/"))
_collection = _client["procurement_db"]["orders"]

# ── Startup data fix — convert BSON Double NaN to null ───────────────────────
# When pandas float64 NaN values are inserted via PyMongo they are stored as
# BSON Double NaN (not BSON null). MongoDB's $sum propagates NaN through the
# whole group even when a $match {$gt: 0} is in place.
# Fix: overwrite every NaN with null once at startup so all aggregations are clean.
# PyMongo passes float('nan') as BSON Double NaN in the query filter, which
# MongoDB matches against stored NaN doubles.
def _fix_nan(field: str) -> None:
    """
    Replace BSON Double NaN in `field` with null.
    Uses an aggregation-pipeline update so NaN detection follows IEEE 754:
    a value is NaN if and only if it is a number that is neither >= 0 nor <= 0.
    Regular query operators ($eq, $gt) are unreliable against BSON NaN across
    MongoDB versions, so we use $gte/$lte inside $expr instead.
    """
    result = _collection.update_many(
        {field: {"$type": "double"}},          # only scan double fields — NaN is always a double
        [{"$set": {field: {"$cond": {
            "if": {"$and": [
                {"$not": [{"$gte": [f"${field}", 0]}]},   # NaN >= 0 is false
                {"$not": [{"$lte": [f"${field}", 0]}]},   # NaN <= 0 is false
            ]},
            "then": None,      # it's NaN → replace with null
            "else": f"${field}"  # valid number → keep as-is
        }}}}]
    )
    if result.modified_count:
        print(f"[startup] Replaced {result.modified_count} NaN values in '{field}' with null")

_fix_nan("total_price")
_fix_nan("unit_price")

# ── In-memory session history (session_id → list of messages) ─────────────────
_histories: dict[str, list] = {}

# ── JSON serializer — handles datetime, ObjectId, NaN, int64, float64 ────────
def _serialize(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        # NaN and Inf are not valid JSON — replace with None so the LLM sees null
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    # numpy int64, float64, pandas NA, etc.
    try:
        f = float(obj)
        if math.isnan(f) or math.isinf(f):
            return None
        return int(f) if f == int(f) else f
    except Exception:
        return str(obj)

# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def get_schema() -> str:
    """
    Returns the schema of the procurement orders collection.
    Call this first if you are unsure which fields to use in a query.
    """
    return """
Collection: procurement_db.orders (~343,000 documents)

Field              | Type     | Description
-------------------|----------|----------------------------------------------
creation_date      | datetime | Date the purchase order was created
purchase_date      | datetime | Date the order was delivered (5% missing)
total_price        | float    | Total order value in USD
unit_price         | float    | Price per unit in USD
quantity           | float    | Number of units ordered
supplier_name      | string   | Supplier company name (title-cased)
department_name    | string   | California state department (title-cased)
item_name          | string   | Ordered item name (lowercased)
acquisition_type   | string   | IT Goods | NON-IT Goods | IT Services | NON-IT Services
acquisition_method | string   | Statewide Contract | Informal Competitive | etc.
fiscal_year        | string   | e.g. "2013-2014"
year               | int      | Calendar year from creation_date (2012–2015)
month              | int      | Month number 1–12 from creation_date
quarter            | int      | Quarter 1–4 from creation_date (Q4 = Apr–Jun, fiscal year-end)

Notes:
- total_price may contain null or negative values — ALWAYS filter with {"total_price": {"$gt": 0}} in every spending query
- quarter values use CALENDAR quarters (pandas dt.quarter): Q1=Jan–Mar, Q2=Apr–Jun, Q3=Jul–Sep, Q4=Oct–Dec
- April–June (fiscal year-end for California) is stored as quarter 2, NOT quarter 4
- Date range: 2012-07-02 to 2015-06-30
"""


@tool
def get_date_range() -> str:
    """
    Returns the earliest and latest creation_date in the orders collection.
    Use this to validate time-based queries before running them.
    """
    result = list(_collection.aggregate([
        {"$group": {
            "_id": None,
            "min_date": {"$min": "$creation_date"},
            "max_date": {"$max": "$creation_date"},
        }}
    ]))
    if not result:
        return "No data found."
    row = result[0]
    return json.dumps({
        "min_date": _serialize(row["min_date"]),
        "max_date": _serialize(row["max_date"]),
    })


@tool
def query_orders(pipeline_json: str) -> str:
    """
    Executes a MongoDB aggregation pipeline on the orders collection and returns results.

    Input: a valid JSON array representing a MongoDB aggregation pipeline.
    Example:
        [{"$match": {"year": 2014, "quarter": 3}}, {"$count": "total"}]

    Rules:
    - Always add a {"$limit": 50} stage at the end of pipelines that may return many documents.
    - Use field names exactly as in the schema (snake_case).
    - For spending queries, ALWAYS use {"$match": {"total_price": {"$gt": 0}}} as the FIRST stage to exclude null, NaN, and negative values.
    """
    # ── Parse ─────────────────────────────────────────────────────────────────
    try:
        pipeline = json.loads(pipeline_json)
        if not isinstance(pipeline, list):
            return "Error: pipeline must be a JSON array."
    except json.JSONDecodeError as e:
        return f"Error: invalid JSON — {e}"

    # ── Validate + sanitize (injects $gt guard, blocks dangerous stages) ──────
    try:
        validated = validate_pipeline(pipeline)
    except ValueError as e:
        return f"Pipeline validation error: {e}"

    # ── Explain the pipeline before execution ─────────────────────────────────
    explanation = explain_query("", validated)

    # ── Execute ───────────────────────────────────────────────────────────────
    try:
        results = list(_collection.aggregate(validated))
        serialized = _serialize(results)
        output = json.dumps(serialized, indent=2)
        if len(output) > 8000:
            output = output[:8000] + "\n... (truncated)"
        data_section = output if results else "No results found for this query."
    except Exception as e:
        return f"MongoDB error: {e}"

    # ── Save key facts to session memory ─────────────────────────────────────
    session_id = _current_session_id.get()
    if session_id and results:
        memory.extract_and_save(session_id, pipeline, results)

    # ── Return explanation + validated pipeline + data ────────────────────────
    pretty_pipeline = json.dumps(validated, indent=2)
    return f"""Reasoning:
{explanation}

MongoDB Pipeline Used:
{pretty_pipeline}

Query Results:
{data_section}"""


# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert AI procurement assistant for California State procurement data.
Your job is to answer user questions by querying a MongoDB collection of purchase orders.

WORKFLOW:
1. Understand the user's question.
2. If stored session context is provided (prefixed "[Stored context]"), use it to resolve
   references like "that quarter", "the same supplier", or "previous result" before querying.
3. If needed, call get_schema() to confirm field names and types.
4. Build a precise MongoDB aggregation pipeline and call query_orders() with it.
   - For multi-step questions (e.g. "top supplier in the highest-spend quarter"),
     run the first pipeline, then use that result to build and run the second pipeline.
5. The tool returns a "Reasoning:" line followed by query results — include the reasoning
   in your answer so the user understands how the result was obtained.
6. Give the user a clear, direct answer with numbers formatted as $X,XXX.XX.

RULES:
- Always use snake_case field names exactly as in the schema.
- For time-based queries: use the `year`, `month`, and `quarter` integer fields — not creation_date string parsing.
- Quarter values are CALENDAR quarters: Q1=Jan–Mar, Q2=Apr–Jun, Q3=Jul–Sep, Q4=Oct–Dec. April–June (California fiscal year-end) is Q2.
- For ALL spending queries: ALWAYS start with {"$match": {"total_price": {"$gt": 0}}}. The validator enforces this, but always include it explicitly.
- Trust the query results — always report the exact value returned. Never say results are unreliable.
- When the user asks about "most ordered", clarify whether they mean by order count or total quantity.
- If results are empty, tell the user clearly and suggest why (e.g., date out of range).
- Never make up numbers — always query first.
- Keep answers concise and professional, as if speaking to a procurement manager.
"""

# ── LLM + Agent setup (LangGraph) ────────────────────────────────────────────
_llm   = ChatOpenAI(model="gpt-5.4-mini", temperature=0)
_tools = [get_schema, get_date_range, query_orders]

# create_react_agent from langgraph.prebuilt — replaces deprecated AgentExecutor
_agent = create_react_agent(
    model=_llm,
    tools=_tools,
    prompt=SYSTEM_PROMPT,
)

# ── Public chat function (called by main.py) ──────────────────────────────────
async def chat(session_id: str, user_message: str) -> str:

    # ── 1. Scope detection ────────────────────────────────────────────────────
    if is_out_of_scope(user_message):
        return out_of_scope_reply()

    # ── 2. Make session_id available inside the query_orders tool ─────────────
    _current_session_id.set(session_id)

    # ── 3. Build message list ─────────────────────────────────────────────────
    history = _histories.setdefault(session_id, [])
    messages = []

    # Inject stored session context so agent can resolve follow-up references
    ctx = memory.context_summary(session_id)
    if ctx:
        messages.append(SystemMessage(content=ctx))

    messages += history + [HumanMessage(content=user_message)]

    # ── 4. Run agent ──────────────────────────────────────────────────────────
    result = await _agent.ainvoke({"messages": messages})
    answer = result["messages"][-1].content

    # ── 5. Update conversation history (keep last 20 messages = 10 turns) ─────
    history.append(HumanMessage(content=user_message))
    history.append(AIMessage(content=answer))
    _histories[session_id] = history[-20:]

    return answer
