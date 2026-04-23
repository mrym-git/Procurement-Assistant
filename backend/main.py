import os
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

load_dotenv()

from agent import chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Procurement Assistant", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


# --- Request / Response models ---

class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str


# --- Routes ---

@app.get("/")
async def serve_ui():
    return FileResponse(os.path.join(frontend_dir, "index.html"))


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    reply = await chat(session_id, req.message.strip())
    return ChatResponse(session_id=session_id, reply=reply)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/session/new")
async def new_session():
    return {"session_id": str(uuid.uuid4())}


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host=host, port=port, reload=True)
