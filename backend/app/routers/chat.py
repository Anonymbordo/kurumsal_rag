from datetime import datetime

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import serialize as S
from ..db import SessionLocal, get_db
from ..deps import current_user
from ..models import Conversation, Message, User
from ..services.assistant import Pending, Reply, answer, plan
from ..timeutil import utcnow

router = APIRouter(prefix="/api/conversations", tags=["sohbet"])


class NewMessage(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    # true: sohbeti cevapsız oluştur; cevap sohbet ekranında akışla (/stream) alınır
    defer: bool = False


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
    # Cevap (dil modeli çağrısı uzun sürebilir) veritabanına yazmadan ÖNCE hesaplanır;
    # böylece yazma kilidi model beklenirken tutulmaz.
    title = body.text.strip().split("\n")[0]
    if body.defer:
        conv = Conversation(user_id=user.id, title=title[:60] + ("…" if len(title) > 60 else ""))
        db.add(conv)
        db.commit()
        return {"conversation": S.conversation(conv), "messages": []}
    reply = answer(db, user, body.text, [])
    conv = Conversation(user_id=user.id, title=title[:60] + ("…" if len(title) > 60 else ""))
    db.add(conv)
    db.flush()
    return {"conversation": S.conversation(conv), "messages": _save(db, conv, body.text, reply)}


@router.get("/{conv_id}/messages")
def messages(conv_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    conv = _own(db, conv_id, user)
    q = select(Message).where(Message.conversation_id == conv.id).order_by(Message.id)
    return {"conversation": S.conversation(conv), "messages": [S.message(m) for m in db.scalars(q)]}


@router.post("/{conv_id}/messages")
def post_message(conv_id: int, body: NewMessage, user: User = Depends(current_user), db: Session = Depends(get_db)):
    conv = _own(db, conv_id, user)
    history = list(db.scalars(select(Message).where(Message.conversation_id == conv.id).order_by(Message.id)))
    reply = answer(db, user, body.text, history)  # önce cevap, sonra yazma (bkz. start)
    return {"messages": _save(db, conv, body.text, reply)}


def _save(db: Session, conv: Conversation, text: str, reply) -> list[dict]:
    user_msg = Message(conversation_id=conv.id, role="user", text=text)
    db.add(user_msg)
    bot_msg = Message(conversation_id=conv.id, role="assistant", text=reply.text, blocks=reply.blocks, sources=reply.sources)
    db.add(bot_msg)
    conv.updated_at = utcnow()
    db.commit()
    return [S.message(user_msg), S.message(bot_msg)]


@router.post("/{conv_id}/messages/stream")
def post_message_stream(conv_id: int, body: NewMessage, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Cevabı akışla döner (NDJSON satırları):
    {"type":"delta","text":"..."} ... {"type":"done","messages":[kullanıcı, asistan]}
    Kullanıcı ilk kelimeyi model bitirmeden görür; toplam süre aynı, beklenen süre kısalır.
    """
    conv = _own(db, conv_id, user)
    history = list(db.scalars(select(Message).where(Message.conversation_id == conv.id).order_by(Message.id)))
    planned = plan(db, user, body.text, history)
    cid, text = conv.id, body.text

    def events():
        reply = planned
        if isinstance(planned, Pending):
            for item in planned.stream():
                if isinstance(item, Reply):
                    reply = item
                else:
                    yield json.dumps({"type": "delta", "text": item}, ensure_ascii=False) + "\n"
        with SessionLocal() as s:  # istek oturumu kapanmış olabilir; kayıt için yeni oturum
            msgs = _save(s, s.get(Conversation, cid), text, reply)
        yield json.dumps({"type": "done", "messages": msgs}, ensure_ascii=False, default=str) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson")
