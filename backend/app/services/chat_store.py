from typing import List, Type

from sqlalchemy.orm import Session
from datetime import datetime
from app.models.conversation import Conversation
from app.models.message import Message

def get_or_create_conversation(db: Session, conversation_id: str) -> Conversation:
    conv = db.query(Conversation).filter_by(conversation_id=conversation_id).first()
    if conv:
        return conv
    conv = Conversation(conversation_id=conversation_id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv

def add_message(db: Session, conversation_id: str, role: str, content: str, route: str | None, input_type: str | None):
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        route=route,
        input_type=input_type
    )
    db.add(msg)
    db.commit()
    return msg

def load_history(db: Session, conversation_id: str, limit: int = 20) -> list[Type[Message]]:
    return (
        db.query(Message)
        .filter_by(conversation_id=conversation_id)
        .order_by(Message.id.asc())
        .limit(limit)
        .all()
    )

def clear_conversation(db: Session, conversation_id: str) -> bool:
    conv = (
        db.query(Conversation)
        .filter_by(conversation_id=conversation_id)
        .first()
    )
    if not conv:
        return False

    db.query(Message).filter_by(
        conversation_id=conversation_id
    ).delete(synchronize_session=False)

    conv.state = {}

    db.commit()
    return True
