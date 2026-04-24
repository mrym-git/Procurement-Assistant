import json
import os
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, Response
from fastapi import Request
from pydantic import BaseModel

load_dotenv()

from agent import chat, chat_stream
from anomaly_detector import detect_anomalies
from chart_builder import build_chart_spec
from query_cache import query_cache
from query_validator import confidence_score
from session_memory import memory
from suggestion_generator import generate_suggestions

# ── App lifespan ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Procurement Assistant API", version="1.0.0", lifespan=lifespan)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Serve frontend ────────────────────────────────────────────────────────────
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")

@app.get("/static/{filename:path}", include_in_schema=False)
async def serve_static(filename: str):
    file_path = os.path.join(frontend_dir, filename)
    return FileResponse(file_path, headers={"Cache-Control": "no-store"})


# ── Request / Response models ─────────────────────────────────────────────────
class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    chart: dict | None = None
    anomalies: list | None = None
    confidence: str | None = None
    suggestions: list | None = None
    results: list | None = None
    cached: bool = False


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def serve_ui():
    """Serve the frontend chat interface."""
    return FileResponse(os.path.join(frontend_dir, "index.html"))


@app.get("/api/health")
async def health():
    """Check that the API and MongoDB are reachable."""
    from pymongo import MongoClient
    from pymongo.errors import ServerSelectionTimeoutError
    try:
        client = MongoClient(
            os.getenv("MONGODB_URI", "mongodb://localhost:27017/"),
            serverSelectionTimeoutMS=2000,
        )
        client.server_info()
        db_status = "connected"
    except ServerSelectionTimeoutError:
        db_status = "unreachable"
    return {"status": "ok", "mongodb": db_status}


@app.get("/api/session/new")
async def new_session():
    """Generate a new session ID for the frontend."""
    return {"session_id": str(uuid.uuid4())}


@app.post("/api/stream")
async def chat_stream_endpoint(req: ChatRequest):
    """
    Streaming chat endpoint — returns Server-Sent Events.
    Each event is a JSON object on a "data: ..." line.
    Event types: token | chart | anomalies | meta | suggestions | cache_hit | error | done
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    session_id = req.session_id or str(uuid.uuid4())

    async def generate():
        # Send session_id as the very first event
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
        async for event in chat_stream(session_id, req.message.strip()):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """
    Main chat endpoint.
    Returns the reply plus chart data, anomalies, confidence, and follow-up suggestions.
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    session_id = req.session_id or str(uuid.uuid4())
    msg = req.message.strip()

    # ── Semantic cache lookup ──────────────────────────────────────────────────
    cached = query_cache.lookup(session_id, msg)
    if cached:
        return ChatResponse(
            session_id=session_id,
            reply=cached["answer"],
            chart=cached.get("chart"),
            anomalies=cached.get("anomalies"),
            confidence=cached.get("confidence"),
            suggestions=cached.get("suggestions"),
            results=cached.get("results"),
            cached=True,
        )

    # ── Run agent ──────────────────────────────────────────────────────────────
    try:
        reply = await chat(session_id, msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    # ── Post-processing ────────────────────────────────────────────────────────
    last_pipeline = memory.get_result(session_id, "last_query_pipeline") or []
    last_results  = memory.get_result(session_id, "last_result_raw")     or []

    chart       = build_chart_spec(last_pipeline, last_results)
    anomalies   = detect_anomalies(last_results) or None
    confidence  = confidence_score(last_pipeline) if last_pipeline else None
    suggestions = generate_suggestions(msg, last_pipeline, last_results)

    # ── Cache for follow-up ────────────────────────────────────────────────────
    query_cache.store(session_id, msg, reply,
                      chart=chart, anomalies=anomalies,
                      confidence=confidence, suggestions=suggestions,
                      results=last_results if last_results else None)

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        chart=chart,
        anomalies=anomalies,
        confidence=confidence,
        suggestions=suggestions,
        results=last_results if last_results else None,
        cached=False,
    )


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host=host, port=port, reload=True)
