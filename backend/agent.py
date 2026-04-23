import json
import os
from datetime import datetime
from typing import Any

from bson import ObjectId
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import tool
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from pymongo import MongoClient

load_dotenv()

# ── MongoDB connection ────────────────────────────────────────────────────────
_client     = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017/"))
_collection = _client["procurement_db"]["orders"]

# ── In-memory session history (session_id → list of messages) ─────────────────
_histories: dict[str, list] = {}

# ── JSON serializer — handles datetime, ObjectId, int64 ──────────────────────
def _serialize(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    try:
        # handles numpy int64, float64, pandas NA, etc.
        return int(obj) if hasattr(obj, '__int__') else float(obj)
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
- total_price has ~30 null values (incomplete/cancelled orders) and some capped outliers at $999,999
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
    - For spending queries, use {"$match": {"total_price": {"$ne": null}}} to exclude nulls.
    """
    try:
        pipeline = json.loads(pipeline_json)
        if not isinstance(pipeline, list):
            return "Error: pipeline must be a JSON array."
    except json.JSONDecodeError as e:
        return f"Error: invalid JSON — {e}"

    try:
        results = list(_collection.aggregate(pipeline))
        serialized = _serialize(results)
        output = json.dumps(serialized, indent=2)
        # Truncate very large outputs to avoid exceeding context limits
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
- For spending queries: filter out null total_price values with $ne: null.
- When the user asks about "most ordered", clarify whether they mean by order count or total quantity.
- If results are empty, tell the user clearly and suggest why (e.g., date out of range).
- Never make up numbers — always query first.
- Keep answers concise and professional, as if speaking to a procurement manager.
"""

# ── LLM + Agent setup ─────────────────────────────────────────────────────────
_llm = ChatOpenAI(model="gpt-4.5-mini", temperature=0)

_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])

_tools = [get_schema, get_date_range, query_orders]

_agent = create_openai_tools_agent(_llm, _tools, _prompt)

_executor = AgentExecutor(
    agent=_agent,
    tools=_tools,
    verbose=True,
    max_iterations=5,
    handle_parsing_errors=True,
)

# ── Public chat function (called by main.py) ──────────────────────────────────
async def chat(session_id: str, user_message: str) -> str:
    history = _histories.setdefault(session_id, [])

    result = await _executor.ainvoke({
        "input": user_message,
        "chat_history": history,
    })

    answer = result["output"]

    # Update session history
    history.append(HumanMessage(content=user_message))
    history.append(AIMessage(content=answer))

    # Keep last 20 messages (10 conversation turns) to manage context size
    _histories[session_id] = history[-20:]

    return answer
