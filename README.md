# 🧠 Procurement Assistant

AI-powered assistant that answers procurement queries using **MongoDB + LLM + Agent Architecture**.

---

## 🚀 Overview
Ask questions like:
- "Top suppliers by spend"
- "Orders in Q3 2014"

The system converts them into MongoDB queries and returns:
- Exact answers
- Charts
- Anomalies
- Suggestions

---

## ✨ Features

### 🤖 AI Agent
- Natural language → MongoDB aggregation pipeline  
- Multi-step reasoning  
- Session memory for follow-ups  

### 🛡️ Validation
- Blocks unsafe MongoDB stages  
- Enforces `total_price > 0`  
- Prevents full collection scans  

### 📊 Visualization
- Auto charts (bar / line)  
- Currency + count formatting  

### ⚠️ Anomaly Detection
- IQR-based outlier detection  
- Flags unusual spending  

### ⚡ Performance
- Semantic cache (Jaccard similarity)  
- Streaming responses (SSE)  

### 💡 UX
- Suggested follow-up questions  
- Confidence indicator  
- CSV export  

---

## ⚙️ Tech Stack
- MongoDB  
- FastAPI (Python)  
- OpenAI (`gpt-5.4-mini`)  
- LangGraph / LangChain  
- HTML / CSS / JavaScript  
- Pandas  

---

## 📂 Project Structure
```

procurement-assistant/
├── backend/
│   ├── agent.py
│   ├── main.py
│   ├── query_validator.py
│   ├── query_explainer.py
│   ├── session_memory.py
│   ├── scope_detector.py
│   ├── chart_builder.py
│   ├── anomaly_detector.py
│   ├── query_cache.py
│   ├── suggestion_generator.py
│   └── reload_data.py
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── explore_data.ipynb
├── requirements.txt
└── README.md

```

---

## 🔄 System Flow
```

User question
↓
Scope Detection
↓
Context Injection
↓
AI Agent (LangGraph)
↓
MongoDB Query
↓
Validation + Explanation + Memory
↓
Final Response (Answer + Chart + Insights)

````

---

## 📊 Dataset
- 335,034 records  
- Cleaned, deduplicated, validated  
- Key fields:
  - total_price
  - supplier_name
  - department_name
  - item_name
  - year, month, quarter  

⚠️ Large transactions (> $100M) are valid government contracts.

---

## ▶️ Run Locally

### 1. Install dependencies
```bash
pip install -r requirements.txt
````

### 2. Start MongoDB

```bash
mongod
```

### 3. Run backend

```bash
cd backend
uvicorn main:app --reload
```

### 4. Open app

```
http://localhost:8000
```

---

## 🧪 Example Queries

* How many orders were placed in Q3 2014?
* Which quarter had the highest spending?
* Top 5 suppliers by total spend
* Department of Transportation spend in 2013
* Orders above $50,000

---

## 📌 API Endpoints

* `POST /api/chat`
* `POST /api/stream`
* `GET /api/health`
* `GET /api/session/new`

---

## 🧠 Key Highlights

* Agent-based architecture (not simple LLM call)
* Pipeline validation before execution
* Explainable reasoning
* Stateful memory
* Smart caching + anomaly insights
