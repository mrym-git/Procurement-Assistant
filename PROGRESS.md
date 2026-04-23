# Procurement Assistant — Project Progress

**Deadline:** 2 days from start
**Goal:** AI-powered assistant that answers natural language procurement queries using MongoDB + LLM

---

## What Is Done ✅

### Phase 1 — Data Preparation (Complete)

| Task | Status | Notes |
|------|--------|-------|
| Load CSV into MongoDB | ✅ Done | `procurement_db.orders`, 343k+ records |
| Explore dataset (EDA) | ✅ Done | `explore_data.ipynb` — full analysis |
| Clean prices | ✅ Done | Stripped `$`/`,`, cast to `float` |
| Clean dates | ✅ Done | Converted to `datetime`, NaT handled |
| Remove duplicates | ✅ Done | 2,084 rows removed |
| Normalize item names | ✅ Done | Lowercased + stripped |
| Normalize supplier/dept names | ✅ Done | Title-cased, casing inconsistencies resolved |
| Rename columns to `snake_case` | ✅ Done | All 31 columns renamed |
| Add helper columns | ✅ Done | `year`, `month`, `quarter` as integers |
| Document schema | ✅ Done | Schema table in notebook |
| Handle outliers | ✅ Done | IQR detection, capped values flagged |
| Distribution analysis | ✅ Done | Histogram, box plot, skewness |
| Time-based analysis | ✅ Done | Orders/year, orders/month, spend trend, spend/quarter |
| Categorical analysis | ✅ Done | Top suppliers, items, acquisition types |
| Quantity analysis | ✅ Done | Top items by total units ordered |
| Relationship analysis | ✅ Done | Spend by supplier, dept, category |
| MongoDB indexes | ✅ Done | 6 single-field + 1 compound `(year, quarter)` |
| Validation before insert | ✅ Done | Null check on critical columns |
| MongoDB error handling | ✅ Done | `try/except` with clear install message |
| `requirements.txt` | ✅ Done | All Python dependencies listed |
| `README.md` | ✅ Done | Setup instructions |

---

### Phase 2 — AI Agent (Backend) (Complete)

**Goal:** Python backend that receives a natural language query, converts it to a MongoDB aggregation pipeline, runs it, and returns an answer.

#### 2.1 — Agent Core (`backend/agent.py`)

| Task | Status | Notes |
|------|--------|-------|
| Agentic framework | ✅ Done | LangGraph `create_react_agent` (replaced deprecated `AgentExecutor`) |
| MongoDB connection | ✅ Done | Connected to `procurement_db.orders` |
| System prompt | ✅ Done | Full schema description + pipeline generation rules |
| `get_schema` tool | ✅ Done | Returns all field names, types, descriptions |
| `get_date_range` tool | ✅ Done | Returns min/max `creation_date` from collection |
| `query_orders` tool | ✅ Done | Executes any aggregation pipeline, serializes results |
| LLM integration | ✅ Done | OpenAI via `ChatOpenAI` (`gpt-5.4-mini`) |
| NaN/null filtering | ✅ Done | Auto-injects `{"$gt": 0}` guard for all spending queries |
| Edge case handling | ✅ Done | Empty results, invalid JSON, MongoDB errors |
| Session history | ✅ Done | Last 20 messages (10 turns) kept per session |

#### 2.2 — FastAPI Backend (`backend/main.py`)

| Task | Status | Notes |
|------|--------|-------|
| `POST /api/chat` | ✅ Done | Accepts `{ session_id, message }`, returns `{ answer }` |
| `GET /api/health` | ✅ Done | Pings MongoDB, reports status |
| `GET /api/session/new` | ✅ Done | Returns fresh UUID session ID |
| CORS | ✅ Done | Enabled for all origins |
| Static file serving | ✅ Done | Serves frontend at `/static/` and `/` |

---

### Phase 3 — Frontend (Complete)

**Goal:** Premium dark-themed chat interface for procurement queries.

**Files:** `frontend/index.html`, `frontend/style.css`, `frontend/app.js`

| Task | Status | Notes |
|------|--------|-------|
| Chat UI layout | ✅ Done | Sidebar + main chat area split layout |
| Message bubbles | ✅ Done | User on right, assistant on left with avatars |
| Input box + send button | ✅ Done | Enter to send, Shift+Enter for newline |
| Loading indicator | ✅ Done | Animated typing dots while waiting |
| Backend connection | ✅ Done | `POST /api/chat` with session ID |
| Answer rendering | ✅ Done | Markdown-style formatting, bold dollar amounts |
| Suggested queries sidebar | ✅ Done | 6 one-click sample questions |
| Health status indicator | ✅ Done | Live dot + polling every 30s |
| New chat button | ✅ Done | Clears history and starts fresh session |
| Glassmorphism design | ✅ Done | Dark bg, blur panels, animated gradient orbs |

---

## What Needs To Be Done 🔲

### Phase 4 — Testing & Evaluation — Day 2

Test the assistant with these queries to verify accuracy:

| Query | Expected behavior | Status |
|-------|------------------|--------|
| "How many orders were placed in Q3 2014?" | Filters `year=2014, quarter=3`, returns count | 🔲 |
| "Which quarter had the highest spending?" | Groups by `year+quarter`, sums `total_price`, returns top 1 | 🔲 |
| "Who are the top 5 suppliers by total spend?" | Groups by `supplier_name`, sums, sorts descending | 🔲 |
| "What are the most frequently ordered items?" | Groups by `item_name`, counts, sorts descending | 🔲 |
| "How much did the Department of Transportation spend in 2013?" | Filters dept + year, sums `total_price` | 🔲 |
| "Show me all NON-IT Goods orders above $50,000" | Filters `acquisition_type` + `total_price > 50000` | 🔲 |
| "What was the total spending in June 2014?" | Filters `year=2014, month=6`, sums | 🔲 |

- [ ] All 7 test queries pass with accurate answers
- [ ] Agent handles follow-up questions in the same session
- [ ] Agent gracefully handles out-of-scope questions

---

## Day-by-Day Plan

### Day 1 ✅ Complete
| Time | Task | Status |
|------|------|--------|
| Morning | Build `agent.py` — LLM tool use loop + MongoDB execution | ✅ Done |
| Afternoon | Build `main.py` — FastAPI `/chat` endpoint + session history | ✅ Done |
| Evening | Build frontend chat UI, connect to backend, test end-to-end | ✅ Done |

### Day 2
| Time | Task | Status |
|------|------|--------|
| Morning | Run all test queries, fix accuracy issues in system prompt | 🔲 |
| Afternoon | Polish UI, add loading states, improve error messages | 🔲 |
| Evening | Final review, clean up code, update `README.md` with run instructions | 🔲 |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Database | MongoDB (`localhost:27017`) |
| LLM | `gpt-5.4-mini` via OpenAI API |
| Agentic Framework | LangGraph — `create_react_agent`, LangChain tools |
| Backend | Python — FastAPI + Uvicorn |
| Frontend | Vanilla HTML/CSS/JS — glassmorphism dark theme |
| Data prep | Pandas, Jupyter |

---

## Key Files

```
procurement-assistant/
├── explore_data.ipynb       ✅ Data prep & EDA
├── backend/
│   ├── agent.py             ✅ LLM agent logic (LangGraph + 3 tools)
│   ├── main.py              ✅ FastAPI server (chat, health, session endpoints)
│   └── requirements.txt     ✅ Backend dependencies
├── frontend/
│   ├── index.html           ✅ Chat UI (sidebar + main area)
│   ├── style.css            ✅ Glassmorphism dark theme
│   └── app.js               ✅ API calls, session management, markdown rendering
├── requirements.txt         ✅ Top-level dependencies
├── README.md                ✅ Setup guide
└── PROGRESS.md              ✅ This file
```

---

## MongoDB Collection Summary

- **Database:** `procurement_db`
- **Collection:** `orders`
- **Documents:** ~343,000
- **Key queryable fields:** `creation_date`, `total_price`, `unit_price`, `quantity`, `supplier_name`, `department_name`, `item_name`, `acquisition_type`, `year`, `month`, `quarter`
- **Indexes:** `creation_date`, `supplier_name`, `total_price`, `department_name`, `year`, `quarter`, `(year, quarter)`
