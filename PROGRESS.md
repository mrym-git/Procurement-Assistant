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

### Phase 5 — Agent Architecture Upgrade (Complete)

Upgraded the system from a basic LLM tool loop into a proper AI agent architecture with validation, reasoning, memory, and scope awareness. **Zero existing code was removed** — only new modules added and `agent.py` minimally patched.

#### New modules created

| File | Purpose |
|---|---|
| `backend/query_validator.py` | `validate_pipeline()` — sanitizes every LLM-generated pipeline before MongoDB execution |
| `backend/query_explainer.py` | `explain_query()` — rule-based NL explanation of what a pipeline does |
| `backend/session_memory.py` | `SessionMemory` class — stateful per-session result store; resolves follow-up references |
| `backend/scope_detector.py` | `is_out_of_scope()` — detects and rejects off-topic questions before agent runs |

#### `query_validator.py` — Pipeline Guardrails

- Blocks dangerous stages: `$lookup`, `$out`, `$merge`, `$function`, `$accumulator`
- Guarantees first stage is always `{$match: {total_price: {$gt: 0}}}` — injects or merges if missing
- Appends `{$limit: 5000}` when no scoping filter (year/month/quarter/supplier/department) is present — prevents full-collection scans
- Raises `ValueError` on malformed pipeline structure

#### `query_explainer.py` — Reasoning Layer

- Rule-based: reads each pipeline stage (`$match`, `$group`, `$sort`, `$limit`, `$count`, `$project`, `$unwind`)
- Produces: `"Reasoning: filtered orders where total_price > 0, year = 2014 -> grouped by (year, quarter) and summed total_price -> sorted by total (highest first) -> limited to top 1 results."`
- Output prepended to tool result so LLM includes reasoning in the final answer

#### `session_memory.py` — Stateful Analytics

- `SessionMemory.save_result(session_id, key, value)` / `get_result(session_id, key)` — generic store
- `extract_and_save()` — auto-inspects pipeline + results, saves:
  - `highest_spend_quarter` → `{year, quarter, total}`
  - `highest_order_quarter` → `{year, quarter, count}`
  - `last_supplier_result` → top supplier list
  - `last_department_result` → top department list
  - `last_query_pipeline` + `last_result_raw`
- `context_summary()` — returns a `[Stored context]` block injected as `SystemMessage` before each turn, enabling the LLM to resolve "that quarter" / "the same supplier" without re-querying

#### `scope_detector.py` — Out-of-Scope Detection

- Regex patterns catch explicit off-topic questions (governor, weather, recipes, sports, etc.)
- Procurement keyword set (60+ terms) fast-paths in-scope detection
- Short inputs (≤4 words) pass through to the agent — handles greetings and follow-ups
- Returns standard reply: *"This assistant only answers questions about the California State procurement dataset."*

#### Changes to `agent.py` (minimal patch, nothing removed)

| Location | Change |
|---|---|
| Imports | Added `contextvars`, `query_explainer`, `query_validator`, `scope_detector`, `session_memory` |
| Module level | Added `_current_session_id` contextvar — passes session_id into tool scope without changing signature |
| `query_orders` body | Replaced manual `$gt` inject with `validate_pipeline()` + `explain_query()` + `memory.extract_and_save()` |
| `query_orders` return | Returns 3-section string: `Reasoning` + `MongoDB Pipeline Used` (validated pipeline as pretty JSON) + `Query Results` |
| `chat()` function | Added scope check → contextvar set → session context `SystemMessage` injection → agent invoke |
| `SYSTEM_PROMPT` | Added multi-step workflow instructions, context resolution rules, reasoning citation rule |

#### `query_orders` tool output format

Every tool call now returns:

```
Reasoning:
<natural language explanation of what the pipeline does>

MongoDB Pipeline Used:
<pretty-printed JSON of the validated pipeline>

Query Results:
<serialized MongoDB results>
```

The pipeline shown is the **validated** one (after `validate_pipeline()` runs), so it always reflects the exact query sent to MongoDB — including any injected `{$gt: 0}` guard or `{$limit: 5000}` stage. This satisfies the assessment requirement: *"generate the appropriate database queries and provide answers."*

#### Request flow after upgrade

```
User question
  -> scope_detector        (off-topic? return standard reply immediately)
  -> session context       (inject [Stored context] as SystemMessage)
  -> LangGraph agent       (may call tools multiple times for multi-step queries)
      -> query_orders
          -> validate_pipeline    (sanitize, inject guards, block dangerous stages)
          -> MongoDB execute
          -> memory.extract_and_save  (store key facts for follow-ups)
          -> return "Reasoning: ... + results"
  -> Final answer (includes reasoning, exact numbers)
```

#### Multi-step query support

For questions like *"Who is the top supplier in the highest-spend quarter?"*:
1. Agent runs pipeline 1 → gets highest-spend quarter → stored in `session_memory`
2. Agent runs pipeline 2 → filters by that quarter → returns top supplier
All automatic — no user prompt engineering required.

---

### Phase 6 — Innovation Features (Complete)

Seven enrichment features added on top of the agent architecture. All served from `/api/chat` as extra JSON fields and rendered client-side.

#### New modules created

| File | Purpose |
|---|---|
| `backend/chart_builder.py` | `build_chart_spec()` — generates Chart.js config from pipeline + results |
| `backend/anomaly_detector.py` | `detect_anomalies()` — IQR-based outlier detection (pure Python) |
| `backend/query_cache.py` | `SemanticCache` — Jaccard similarity cache with stemming (threshold 0.55) |
| `backend/suggestion_generator.py` | `generate_suggestions()` — rule-based follow-up question generator |

#### Features

| Feature | How It Works |
|---|---|
| **Chart rendering** | `chart_builder.py` inspects `_id` type: dict with `month` → line chart, `quarter` → bar, string → horizontal bar. Returns Chart.js config with `"format": "currency"/"count"/"number"` hint. Frontend attaches JS formatter callbacks (tick labels, tooltips). |
| **Follow-up suggestions** | `suggestion_generator.py` reads pipeline JSON to detect context (quarterly/monthly/supplier/dept/item) and returns 3 targeted clickable chips. |
| **Streaming responses** | `chat_stream()` async generator + `POST /api/stream` SSE endpoint. Emits `token`, `chart`, `anomalies`, `meta`, `suggestions`, `cache_hit`, `error`, `done` event types. |
| **Semantic query cache** | `SemanticCache.lookup()` tokenizes + stems question, computes Jaccard similarity, returns cached entry if ≥ 0.55. Avoids redundant MongoDB + LLM calls. Numbers kept as tokens so "Q3 2014" ≠ "Q2 2014". |
| **Anomaly flagging** | IQR fence (Q3 + 1.5×IQR). Requires ≥4 data points, value must be both above fence AND ≥3× median. Capped at 5 outliers. Skips `_id=None` documents. |
| **CSV export button** | Frontend renders download button on assistant messages. Flattens `_id` dicts, generates CSV blob. |
| **Confidence indicator** | `confidence_score()` counts specific `$match` fields. ≥2 → High (green), 1 → Medium (amber), 0 → Low (red). Shown as colored pill below each answer. |

#### `/api/chat` response shape (extended)

```json
{
  "session_id": "...",
  "reply": "...",
  "chart": { "type": "bar", "data": {...}, "options": {...}, "format": "currency" },
  "anomalies": [{ "label": "...", "value": 1.2e10, "threshold": 3e9 }],
  "confidence": "High" | "Medium" | "Low",
  "suggestions": ["...", "...", "..."],
  "cached": false
}
```

#### Frontend additions (`app.js`, `style.css`, `index.html`)

- `renderChart(bubble, chartConfig)` — injects Chart.js canvas, attaches formatter callbacks
- `renderAnomalies(bubble, anomalies)` — warning banner with outlier values
- `renderMeta(bubble, confidence, isCached)` — confidence pill + ⚡ Cached badge
- `renderSuggestions(bubble, suggestions)` — clickable follow-up chips
- `renderCsvButton(bubble, results)` — CSV download button
- Chart.js 4.4 loaded via CDN in `index.html`

#### Key bugs fixed during Phase 6

| Bug | Root Cause | Fix |
|---|---|---|
| All enrichment fields returned `null` | `contextvars.ContextVar` doesn't propagate through LangGraph's async context — `session_id` was `""` in tool, so `memory.extract_and_save()` was never called | Replaced contextvar with module-level `_active_session = {"id": ""}` dict (asyncio is single-threaded) |
| "Unknown ($111,675)" anomaly on supplier query | `_id=None` documents (summary rows) passed anomaly check | Skip any result where `_id is None` |
| 16 outliers flagged on department query | IQR fence too sensitive for skewed distributions | Added 3× median requirement; capped at 5 max |
| Hardcoded "Medi-Cal" message on all anomaly banners | Frontend always appended fixed text | Removed hardcoded suffix — banner now dynamic |
| Old server process (PID) intercepting requests | Windows TCP FIN_WAIT2 kept old process alive on port 8000 | Kill all `python.exe` processes before restart |
| Anomaly label showed raw dict: "month=3" | `_id` dict was joined as `k=v` pairs with no human formatting | Added `_format_label()` — converts to "Mar 2014", "Q2 2015", etc. |
| Hardcoded "likely large Medi-Cal managed care contracts" on all anomaly banners | Frontend always appended fixed text regardless of query context | Removed hardcoded suffix entirely |

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
| Evening | Agent architecture upgrade — validator, explainer, memory, scope detector | ✅ Done |

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
│   ├── agent.py                 ✅ LangGraph agent + architecture layers integrated
│   ├── main.py                  ✅ FastAPI server (chat, health, session endpoints)
│   ├── query_validator.py       ✅ Pipeline guardrails (sanitize, inject guards, block dangerous stages)
│   ├── query_explainer.py       ✅ Rule-based NL reasoning explanation
│   ├── session_memory.py        ✅ Stateful per-session result store + context injection
│   ├── scope_detector.py        ✅ Out-of-scope question detection
│   ├── chart_builder.py         ✅ Chart.js config generator (line/bar/horizontal bar)
│   ├── anomaly_detector.py      ✅ IQR outlier detection (pure Python)
│   ├── query_cache.py           ✅ Jaccard semantic cache with stemming
│   ├── suggestion_generator.py  ✅ Rule-based follow-up question generator
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
