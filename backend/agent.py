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

load_dotenv()

# ── MongoDB connection ────────────────────────────────────────────────────────
_client     = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017/"))
_collection = _client["procurement_db"]["orders"]

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
- total_price may contain null, NaN, or negative values — ALWAYS filter with {"total_price": {"$gt": 0}} in every spending query
- quarter 4 (April–June) is always the highest-spending quarter due to fiscal year-end
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
    try:
        pipeline = json.loads(pipeline_json)
        if not isinstance(pipeline, list):
            return "Error: pipeline must be a JSON array."
    except json.JSONDecodeError as e:
        return f"Error: invalid JSON — {e}"

    # Auto-inject total_price guard at the front of the pipeline.
    # Condition: pipeline references total_price AND the very first stage is not
    # already a $match with {total_price: {$gt: 0}}.
    # We check only the first stage so that a $gt on a different field (e.g. unit_price)
    # or a $gt placed after a $group does NOT suppress the injection.
    pipeline_str = json.dumps(pipeline)
    if "total_price" in pipeline_str:
        first_stage_is_guard = (
            pipeline
            and "$match" in pipeline[0]
            and pipeline[0]["$match"].get("total_price", {}).get("$gt") == 0
        )
        if not first_stage_is_guard:
            pipeline = [{"$match": {"total_price": {"$gt": 0}}}] + pipeline

    try:
        results = list(_collection.aggregate(pipeline))
        serialized = _serialize(results)
        output = json.dumps(serialized, indent=2)
        if len(output) > 8000:
            output = output[:8000] + "\n... (truncated)"
        return output if results else "No results found for this query."
    except Exception as e:
        return f"MongoDB error: {e}"


# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert AI procurement assistant for California State procurement data.
Your job is to answer user questions by querying a MongoDB collection of purchase orders.

WORKFLOW:
1. Understand the user's question.
2. If needed, call get_schema() to confirm field names and types.
3. Build a precise MongoDB aggregation pipeline and call query_orders() with it.
4. Interpret the results and give the user a clear, direct answer.
5. Always include numbers, amounts (formatted as $X,XXX.XX), and named entities in your answer.

RULES:
- Always use snake_case field names exactly as in the schema.
- For time-based queries: use the `year`, `month`, and `quarter` integer fields — not creation_date string parsing.
- For ALL spending queries: ALWAYS start with {"$match": {"total_price": {"$gt": 0}}} to exclude null, NaN, and negative values. Never skip this step.
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
    history = _histories.setdefault(session_id, [])

    # Build message list: system context is handled by the agent prompt
    messages = history + [HumanMessage(content=user_message)]

    result = await _agent.ainvoke({"messages": messages})

    # Last message in the result is the assistant's final answer
    answer = result["messages"][-1].content

    # Update session history (keep last 20 messages = 10 turns)
    history.append(HumanMessage(content=user_message))
    history.append(AIMessage(content=answer))
    _histories[session_id] = history[-20:]

    return answer
