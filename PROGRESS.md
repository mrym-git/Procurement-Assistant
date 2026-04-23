# Procurement Assistant — Project Progress

**Deadline:** 2 days from start
**Goal:** AI-powered assistant that answers natural language procurement queries using MongoDB + LLM

---

## What Is Done ✅

### Phase 1 — Data Preparation (Complete)

| Task | Status | Notes |
|------|--------|-------|
| Load CSV into MongoDB | ✅ Done | `procurement_db.orders`, 335k records after cleaning |
| Explore dataset (EDA) | ✅ Done | `explore_data.ipynb` — full analysis |
| Clean prices | ✅ Done | Stripped `$`/`,`, cast via `pd.to_numeric(errors='coerce')` |
| Clean dates | ✅ Done | Converted to `datetime`, NaT handled |
| Remove duplicates | ✅ Done | 2,084 rows removed |
| Normalize item names | ✅ Done | Lowercased + stripped |
| Normalize supplier/dept names | ✅ Done | Title-cased, 258 casing inconsistencies resolved |
| Rename columns to `snake_case` | ✅ Done | All 31 columns renamed |
| Add helper columns | ✅ Done | `year`, `month`, `quarter` as integers |
| Document schema | ✅ Done | Schema table in notebook with quarter mapping clarification |
| Handle outliers | ✅ Done | IQR detection; confirmed large values are legitimate Medi-Cal contracts |
| Distribution analysis | ✅ Done | Histogram, box plot, skewness |
| Time-based analysis | ✅ Done | Orders/year, orders/month, spend trend, spend/quarter |
| Categorical analysis | ✅ Done | Top suppliers, items, acquisition types |
| Quantity analysis | ✅ Done | Top items by total units ordered |
| Relationship analysis | ✅ Done | Spend by supplier, dept, category |
| MongoDB indexes | ✅ Done | 6 single-field + 1 compound `(year, quarter)` |
| Validation before insert | ✅ Done | Assert 0 NaN / 0 Inf before load |
| MongoDB error handling | ✅ Done | `try/except` with clear install message |
| `requirements.txt` | ✅ Done | All Python dependencies listed |
| `README.md` | ✅ Done | Setup instructions |

#### Null Handling Strategy (applied in notebook)

| Column | Null Rate | Strategy |
|---|---|---|
| `requisition_number` | ~96% | Dropped — too sparse |
| `sub_acquisition_method` | ~91% | Dropped — too sparse |
| `sub_acquisition_type` | ~80% | Dropped — too sparse |
| `lpa_number` | ~73% | Dropped — too sparse |
| `supplier_qualifications` | ~59% | Dropped — too sparse |
| `supplier_zip_code` | ~20% | Filled with `"Unknown"` |
| `location` | ~20% | Filled with `"Unknown"` |
| `purchase_date` | ~5% | Kept as-is (not used in aggregations) |
| `total_price` | ~0.009% | Rows dropped — required for spending queries |
| `creation_date` | 0% | No action needed |

#### Data Reload Fix (`backend/reload_data.py`)

A full clean reload was performed after discovering BSON Double NaN values in MongoDB:

- **Root cause:** `df.where(df.notna(), None)` silently fails on `float64` columns — pandas cannot store `None` in a float array, so `NaN` stayed as `float('nan')` and PyMongo wrote it as BSON Double NaN. MongoDB's `$sum` then propagated NaN through the whole aggregation.
- **Fix:** rows where `total_price` is `NaN` or `<= 0` are now dropped **before insertion** using `df[df['total_price'].notna() & (df['total_price'] > 0)]`.
- **Result:** 8,987 rows removed (30 NaN + 7,387 zero + 570 negative). Final collection: **335,034 records**, 0 NaN, 0 null, 0 negative.

#### Outlier Investigation

- Max `total_price`: **$7,337,038,064** (Delta Dental — Dept. of Health Care Services)
- 217 orders > $100M account for **68% of all reported spend**
- **Confirmed legitimate:** all large orders are Medi-Cal managed care contracts (Delta Dental, Health Net, L.A. Care, County of LA, etc.)
- No capping or removal applied — data is accurate for government health contracting

---

### Phase 2 — AI Agent (Backend) (Complete)

**Goal:** Python backend that receives a natural language query, converts it to a MongoDB aggregation pipeline, runs it, and returns an answer.

#### 2.1 — Agent Core (`backend/agent.py`)

| Task | Status | Notes |
|------|--------|-------|
| Agentic framework | ✅ Done | LangGraph `create_react_agent` (replaced deprecated `AgentExecutor`) |
| MongoDB connection | ✅ Done | Connected to `procurement_db.orders` |
| System prompt | ✅ Done | Full schema + pipeline rules + quarter mapping clarification |
| `get_schema` tool | ✅ Done | Returns all field names, types, descriptions |
| `get_date_range` tool | ✅ Done | Returns min/max `creation_date` from collection |
| `query_orders` tool | ✅ Done | Executes any aggregation pipeline, serializes results |
| LLM integration | ✅ Done | OpenAI via `ChatOpenAI` (`gpt-5.4-mini`) |
| NaN serializer fix | ✅ Done | `_serialize()` uses `math.isnan()` — returns `None` instead of string `"nan"` |
| Auto-inject guard | ✅ Done | Checks first pipeline stage; always injects `{$gt: 0}` at front if missing |
| Edge case handling | ✅ Done | Empty results, invalid JSON, MongoDB errors |
| Session history | ✅ Done | Last 20 messages (10 turns) kept per session |

#### Bug fixes applied to `agent.py`

| Bug | Root Cause | Fix |
|---|---|---|
| Agent returned `"nan"` string | `_serialize()` passed `float('nan')` through `int()` → `ValueError` → `str(nan)` | Explicit `math.isnan()` check before any numeric conversion |
| Auto-inject skipped when `$gt` appeared anywhere | Checked for `"$gt"` anywhere in pipeline JSON string | Now checks only if first stage is already `{total_price: {$gt: 0}}` |
| Schema said "Q4 = April–June" | Incorrect — pandas `dt.quarter` uses calendar quarters | Corrected: April–June = **Q2**, not Q4 |
| Tool docstring said `$ne: null` | `$ne: null` does not catch BSON Double NaN | Updated to `$gt: 0` to match actual behavior |

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

### Phase 4 — Testing & Debugging (Complete)

All 7 test queries verified against the live system:

| Query | Result | Status |
|-------|--------|--------|
| "How many orders were placed in Q3 2014?" | 28,270 orders | ✅ |
| "Which quarter had the highest spending?" | 2015-Q2 → $28,804,774,748.58 | ✅ |
| "Who are the top 5 suppliers by total spend?" | Health Care Services-dominated contracts | ✅ |
| "What are the most frequently ordered items?" | Medical supplies, toner, office supplies | ✅ |
| "How much did the Department of Transportation spend in 2013?" | Clean dollar total returned | ✅ |
| "Show me all NON-IT Goods orders above $50,000" | Correct filtered results | ✅ |
| "What was the total spending in June 2014?" | Clean monthly spend returned | ✅ |

#### Bugs found and fixed during testing

| Issue | Root cause | Fix |
|---|---|---|
| All spending queries returned `nan` | BSON Double NaN stored in `total_price` from original pandas insert | Full data reload via `reload_data.py` — drops NaN/zero rows before insert |
| Agent reported "result not reliable" | Schema had wrong quarter mapping (said Q4=Apr-Jun, data has Q2=Apr-Jun) | Corrected quarter note in schema tool and system prompt |
| `_serialize` returned `"nan"` string | Fallback `str(nan)` in serializer | Fixed with `math.isnan()` guard returning `None` |
| Agent ignored `$gt` guard | Auto-inject checked for `$gt` anywhere in pipeline | Fixed to check only the first stage |

---

## Day-by-Day Plan

### Day 1 ✅ Complete
| Time | Task | Status |
|------|------|--------|
| Morning | Build `agent.py` — LLM tool use loop + MongoDB execution | ✅ Done |
| Afternoon | Build `main.py` — FastAPI `/chat` endpoint + session history | ✅ Done |
| Evening | Build frontend chat UI, connect to backend, test end-to-end | ✅ Done |

### Day 2 ✅ Complete
| Time | Task | Status |
|------|------|--------|
| Morning | Run test queries, fix NaN bug, reload data, fix quarter mapping | ✅ Done |
| Afternoon | Outlier investigation, data quality audit, null handling improvements | ✅ Done |
| Evening | Final review, clean up code | 🔲 |

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
├── explore_data.ipynb           ✅ Data prep, EDA, null handling, MongoDB load
├── backend/
│   ├── agent.py                 ✅ LangGraph agent + 3 tools + NaN serializer fix
│   ├── main.py                  ✅ FastAPI server (chat, health, session endpoints)
│   ├── reload_data.py           ✅ Clean data reload script (drops NaN/zero rows)
│   ├── fix_nan.py               ✅ One-time BSON NaN repair utility
│   └── requirements.txt         ✅ Backend dependencies
├── frontend/
│   ├── index.html               ✅ Chat UI (sidebar + main area)
│   ├── style.css                ✅ Glassmorphism dark theme
│   └── app.js                   ✅ API calls, session management, markdown rendering
├── requirements.txt             ✅ Top-level dependencies
├── README.md                    ✅ Setup guide
└── PROGRESS.md                  ✅ This file
```

---

## MongoDB Collection Summary

- **Database:** `procurement_db`
- **Collection:** `orders`
- **Documents:** 335,034 (after removing NaN, zero, negative, and duplicate rows)
- **Key queryable fields:** `creation_date`, `total_price`, `unit_price`, `quantity`, `supplier_name`, `department_name`, `item_name`, `acquisition_type`, `year`, `month`, `quarter`
- **Indexes:** `creation_date`, `supplier_name`, `total_price`, `department_name`, `year`, `quarter`, `(year, quarter)`
- **Quarter mapping:** Calendar quarters — Q1=Jan–Mar, Q2=Apr–Jun, Q3=Jul–Sep, Q4=Oct–Dec
- **Spend note:** 217 orders > $100M account for 68% of all spend — confirmed legitimate Medi-Cal managed care contracts
