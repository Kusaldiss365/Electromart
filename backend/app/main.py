from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from app.core.db import Base, engine, get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.agents.graph import build_graph

from fastapi.middleware.cors import CORSMiddleware

# Import models so Base.metadata knows them
import app.models  # noqa
from app.services.chat_store import get_or_create_conversation, load_history, add_message, clear_conversation

app = FastAPI(title="ElectroMart Multi-Agent Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",     # sometimes Next.js uses 3001 on reload
        "*"                          # ← temporary test wildcard (remove later)
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE"],  # be explicit first
    allow_headers=["Content-Type", "Authorization", "*"],
    expose_headers=["*"],
    max_age=600,
)


# Create tables (simple for assessment; Alembic optional)
Base.metadata.create_all(bind=engine)

graph = build_graph()

@app.get("/")
def health():
    return {"status": "ok"}

@app.post("/chat")
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    # 1) Conversation row (holds memory/state)
    conversation = get_or_create_conversation(db, req.conversation_id)

    # 2) Load recent chat history for context
    history_rows = load_history(db, req.conversation_id, limit=20)
    history = [{"role": r.role, "content": r.content} for r in history_rows]

    # 3) Load persistent agent memory (ticket id, order id, etc.)
    memory = conversation.state or {}

    # 4) Persist user message
    add_message(db, req.conversation_id, "user", req.message, None, req.input_type)

    # 5) Run graph (router -> agent)
    out = graph.invoke(
        {
            "message": req.message,
            "history": history,
            "memory": memory,
            "db": db,
            "route": "",
            "response": "",
        }
    )

    # 6) Persist updated memory/state safely
    conversation.state = out.get("memory", memory)
    db.commit()

    # 7) Persist assistant message
    add_message(db, req.conversation_id, "assistant", out["response"], out["route"], None)

    # 8) Return to frontend
    return {"route": out["route"], "response": out["response"]}


#refresh chat
@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    rows = load_history(db, conversation_id, limit=200)
    return {
      "conversation_id": conversation_id,
      "messages": [
        {"role": r.role, "text": r.content, "route": r.route, "created_at": r.created_at.isoformat()}
        for r in rows
      ]
    }

@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)):
    ok = clear_conversation(db, conversation_id)
    if not ok:
        return {"ok": False, "message": "Conversation not found"}
    return {"ok": True, "message": "Conversation cleared"}


