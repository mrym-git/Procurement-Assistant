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

## What Needs To Be Done 🔲

### Phase 2 — AI Agent (Backend) — Day 1

**Goal:** Python backend that receives a natural language query, converts it to a MongoDB aggregation pipeline, runs it, and returns an answer.

---

#### 2.1 — Agent Core (`backend/agent.py`)

- [ ] Connect to MongoDB (`procurement_db.orders`)
- [ ] Build system prompt that describes the schema and instructs the LLM to generate MongoDB queries
- [ ] Implement the agentic loop:
  1. User sends a natural language message
  2. LLM generates a MongoDB aggregation pipeline (as JSON)
  3. Backend executes the pipeline
  4. Result passed back to LLM to formulate a natural language answer
- [ ] Handle edge cases: empty results, invalid queries, ambiguous questions
- [ ] Use **OpenAI API** (`gpt-4.5-mini`)

**Suggested tools to expose to the agent:**
| Tool | Purpose |
|------|---------|
| `query_orders` | Run any aggregation pipeline on `orders` |
| `get_schema` | Return field names and types |
| `get_date_range` | Return min/max `creation_date` |

---

#### 2.2 — FastAPI Backend (`backend/main.py`)

- [ ] `POST /chat` — accepts `{ session_id, message }`, returns `{ answer }`
- [ ] `GET /health` — confirms API and MongoDB are up
- [ ] CORS enabled for frontend
- [ ] Session-based conversation history (last N messages passed to LLM for context)

---

### Phase 3 — Frontend — Day 1–2

**Goal:** Clean chat interface where users can ask procurement questions and see answers.

**Files:** `frontend/index.html`, `frontend/style.css`, `frontend/app.js`

- [ ] Chat UI with message bubbles (user on right, assistant on left)
- [ ] Input box + send button (Enter key support)
- [ ] Loading indicator while waiting for response
- [ ] Connect to `POST /chat` on the backend
- [ ] Display assistant answer clearly
- [ ] Optional: show the MongoDB query that was generated (collapsible)

---

### Phase 4 — Testing & Evaluation — Day 2

Test the assistant with these queries to verify accuracy:

| Query | Expected behavior |
|-------|------------------|
| "How many orders were placed in Q3 2014?" | Filters `year=2014, quarter=3`, returns count |
| "Which quarter had the highest spending?" | Groups by `year+quarter`, sums `total_price`, returns top 1 |
| "Who are the top 5 suppliers by total spend?" | Groups by `supplier_name`, sums, sorts descending |
| "What are the most frequently ordered items?" | Groups by `item_name`, counts, sorts descending |
| "How much did the Department of Transportation spend in 2013?" | Filters dept + year, sums `total_price` |
| "Show me all NON-IT Goods orders above $50,000" | Filters `acquisition_type` + `total_price > 50000` |
| "What was the total spending in June 2014?" | Filters `year=2014, month=6`, sums |

- [ ] All 7 test queries pass with accurate answers
- [ ] Agent handles follow-up questions in the same session
- [ ] Agent gracefully handles out-of-scope questions

---

## Day-by-Day Plan

### Day 1
| Time | Task |
|------|------|
| Morning | Build `agent.py` — LLM tool use loop + MongoDB execution |
| Afternoon | Build `main.py` — FastAPI `/chat` endpoint + session history |
| Evening | Build frontend chat UI, connect to backend, test end-to-end |

### Day 2
| Time | Task |
|------|------|
| Morning | Run all test queries, fix accuracy issues in system prompt |
| Afternoon | Polish UI, add loading states, improve error messages |
| Evening | Final review, clean up code, update `README.md` with run instructions |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Database | MongoDB (`localhost:27017`) |
| LLM | GPT-4.5-mini (`gpt-4.5-mini`) via OpenAI API |
| Backend | Python — FastAPI |
| Frontend | Vanilla HTML/CSS/JS |
| Data prep | Pandas, Jupyter |

---

## Key Files

```
procurement-assistant/
├── explore_data.ipynb       ✅ Data prep & EDA
├── backend/
│   ├── agent.py             🔲 LLM agent logic
│   ├── main.py              🔲 FastAPI server
│   └── requirements.txt     ✅ Backend dependencies
├── frontend/
│   ├── index.html           🔲 Chat UI
│   ├── style.css            🔲 Styling
│   └── app.js               🔲 API calls & chat logic
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
