from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import serialize as S
from ..db import get_db
from ..deps import current_user
from ..models import Conversation, Message, User
from ..services.assistant import answer
from ..timeutil import utcnow

router = APIRouter(prefix="/api/conversations", tags=["sohbet"])


class NewMessage(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


def _own(db: Session, conv_id: int, user: User) -> Conversation:
    c = db.get(Conversation, conv_id)
    if c is None or c.user_id != user.id:
        raise HTTPException(404, "Sohbet bulunamadı")
    return c


@router.get("")
def list_conversations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc())
    return [S.conversation(c) for c in db.scalars(q)]


@router.post("")
def start(body: NewMessage, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """İlk mesajla yeni sohbet başlatır ve asistanın yanıtını döner."""
    title = body.text.strip().split("\n")[0]
    conv = Conversation(user_id=user.id, title=title[:60] + ("…" if len(title) > 60 else ""))
    db.add(conv)
    db.flush()
    reply = _send(db, conv, user, body.text)
    return {"conversation": S.conversation(conv), "messages": reply}


@router.get("/{conv_id}/messages")
def messages(conv_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    conv = _own(db, conv_id, user)
    q = select(Message).where(Message.conversation_id == conv.id).order_by(Message.id)
    return {"conversation": S.conversation(conv), "messages": [S.message(m) for m in db.scalars(q)]}


@router.post("/{conv_id}/messages")
def post_message(conv_id: int, body: NewMessage, user: User = Depends(current_user), db: Session = Depends(get_db)):
    conv = _own(db, conv_id, user)
    return {"messages": _send(db, conv, user, body.text)}


def _send(db: Session, conv: Conversation, user: User, text: str) -> list[dict]:
    history = list(db.scalars(select(Message).where(Message.conversation_id == conv.id).order_by(Message.id)))
    user_msg = Message(conversation_id=conv.id, role="user", text=text)
    db.add(user_msg)
    reply = answer(db, user, text, history)
    bot_msg = Message(conversation_id=conv.id, role="assistant", text=reply.text, blocks=reply.blocks, sources=reply.sources)
    db.add(bot_msg)
    conv.updated_at = utcnow()
    db.commit()
    return [S.message(user_msg), S.message(bot_msg)]
