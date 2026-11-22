"""Sohbet asistanı.

Görev, paylaşılan doküman ve teslim tarihi soruları doğrudan veritabanından,
yapılandırılmış kartlarla yanıtlanır (uydurma riski yok, her yanıt kaynaklı).
Bunların dışındaki serbest sorular LLM sağlayıcısına gider.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..llm import ChatTurn, get_provider
from ..models import Document, Message, Task, User
from .load import load_pct
from ..timeutil import utcnow

TASK_KEY = re.compile(r"\b([A-Za-zÇĞİÖŞÜçğıöşü]{1,6}-\d+)\b")
MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def tr_lower(s: str) -> str:
    return s.replace("I", "ı").replace("İ", "i").lower()


def tr_date(d: date | None) -> str:
    return f"{d.day} {MONTHS[d.month - 1]}" if d else "—"


@dataclass
class Reply:
    text: str
    blocks: list = field(default_factory=list)
    sources: list = field(default_factory=list)


def _users(db: Session) -> dict[str, User]:
    return {u.id: u for u in db.scalars(select(User))}


def _task_card(db: Session, t: Task, users: dict[str, User], me: User) -> dict:
    assigned_by = users.get(t.assigned_by or t.decided_by or "")
    doc = db.get(Document, t.document_id) if t.document_id else None
    recent = t.assigned_at and utcnow() - t.assigned_at < timedelta(days=2)
    note = ""
    if t.suggested_assignee_id and t.suggested_assignee_id != me.id:
        first = users.get(t.suggested_assignee_id)
        if first:
            load = load_pct(db, first)
            why = f" o kişi bu sprintte %{load} dolu olduğu için" if load >= 90 else ""
            note = f"Bu görev ilk olarak {first.name} için önerilmişti;{why} liderin sana verdi."
    return {
        "id": t.id,
        "key": t.key or f"#{t.id}",
        "title": t.title,
        "tag": "Yeni atandı" if recent else ("Tamamlandı" if t.status == "done" else "Devam ediyor"),
        "tone": "new" if recent else ("done" if t.status == "done" else "active"),
        "assigned_by": assigned_by.name if assigned_by else "—",
        "due": tr_date(t.due_date),
        "source": f"{doc.title} {t.source_ref}".strip() if doc else (t.source_ref or "—"),
        "document_id": t.document_id,
        "note": note,
    }


def _my_active_tasks(db: Session, me: User) -> list[Task]:
    q = select(Task).where(Task.assignee_id == me.id, Task.status.in_(("accepted", "exported")))
    return sorted(db.scalars(q), key=lambda t: (t.due_date or date.max))


def _shared_docs(db: Session, me: User, days: int = 7) -> list[Document]:
    since = utcnow() - timedelta(days=days)
    docs = db.scalars(select(Document).where(Document.created_at >= since)).all()
    return [d for d in docs if me.id in (d.shared_with or []) and d.uploaded_by != me.id]


def answer(db: Session, me: User, text: str, history: list[Message]) -> Reply:
    q = tr_lower(text)
    users = _users(db)
    parts: list[str] = []
    blocks: list[dict] = []
    sources: list[str] = []

    wants_tasks = "görev" in q and any(w in q for w in ("bana", "benim", "bugün", "üzerimde", "görevlerim"))
    wants_shared = "paylaş" in q
    wants_due = "teslim" in q or "bu hafta" in q
    key_match = TASK_KEY.search(text)
    wants_why = "neden" in q and key_match is not None

    if wants_why:
        key = key_match.group(1).upper()
        t = db.scalar(select(Task).where(Task.key == key))
        if t is None:
            parts.append(f"{key} anahtarlı bir görev bulamadım.")
        else:
            sug = users.get(t.suggested_assignee_id or "")
            parts.append(f"{key} için modelin gerekçeleri: " + "; ".join(t.reasons) + ".")
            if sug and t.assignee_id != sug.id:
                parts.append(
                    f"Model önce {sug.name} kişisini önermişti; liderin kararıyla atama değişti."
                )
            sources.append(f"Görev {key} · öneri kaydı")

    if wants_tasks:
        tasks = _my_active_tasks(db, me)
        if tasks:
            new = sum(1 for t in tasks if t.assigned_at and utcnow() - t.assigned_at < timedelta(days=2))
            line = f"Şu an üzerinde **{len(tasks)} aktif görev** var."
            if new:
                line += f" {new} tanesi sana yeni atandı."
            parts.append(line)
            blocks.append({"type": "tasks", "items": [_task_card(db, t, users, me) for t in tasks]})
            sources.append("İş takibi: " + ", ".join(t.key or f"#{t.id}" for t in tasks))
        else:
            parts.append("Şu an sana atanmış aktif bir görev yok.")

    if wants_due and not wants_tasks:
        end = date.today() + timedelta(days=7)
        tasks = [t for t in _my_active_tasks(db, me) if t.due_date and t.due_date <= end]
        parts.append(
            f"Önümüzdeki 7 günde teslim tarihi olan **{len(tasks)} görevin** var."
            if tasks
            else "Önümüzdeki 7 günde teslim tarihi olan görevin yok."
        )
        if tasks:
            blocks.append({"type": "tasks", "items": [_task_card(db, t, users, me) for t in tasks]})

    if wants_shared:
        docs = _shared_docs(db, me)
        if docs:
            parts.append(f"Son 7 günde seninle **{len(docs)} doküman** paylaşıldı:")
            blocks.append(
                {
                    "type": "documents",
                    "items": [
                        {
                            "id": d.id,
                            "title": d.title,
                            "shared_by": d.uploader.name if d.uploader else "—",
                            "at": d.created_at.isoformat(),
                            "related": d.related_task_key,
                        }
                        for d in docs
                    ],
                }
            )
            sources.append("Paylaşılan dokümanlar")
        else:
            parts.append("Son 7 günde seninle paylaşılan yeni bir doküman yok.")

    if parts:
        return Reply(text="\n\n".join(parts), blocks=blocks, sources=sources)

    turns = [ChatTurn(m.role, m.text) for m in history] + [ChatTurn("user", text)]
    return Reply(text=get_provider().chat(turns, context=""), sources=[])
