from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import serialize as S
from ..db import get_db
from ..deps import current_user, require_lead
from ..models import Document, Task, User
from ..services import audit
from ..services.extraction import promote_candidate
from ..services.load import load_pct
from ..services.titles import display_title
from ..timeutil import utcnow

router = APIRouter(prefix="/api/tasks", tags=["görevler"])


class Decision(BaseModel):
    action: Literal["pick", "accept", "reject", "undo", "promote", "dismiss", "share"]
    assignee_id: str | None = None
    reason: Literal["not_task", "not_now"] | None = None  # reject için


@router.post("/{task_id}/decision")
def decide(task_id: int, body: Decision, user: User = Depends(require_lead), db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if t is None or t.team_id != user.team_id:
        raise HTTPException(404, "Görev bulunamadı")
    if t.status in ("exported", "done"):
        raise HTTPException(409, "Aktarılmış görev bu ekrandan değiştirilemez")

    if t.status in ("candidate", "dismissed", "announcement", "announced") and body.action not in (
        "promote", "dismiss", "undo", "share"
    ):
        raise HTTPException(409, "Önce bu cümlenin görev olup olmadığına karar verin")
    if body.action == "share" and t.kind != "announcement":
        raise HTTPException(409, "Yalnızca duyurular ekiple paylaşılabilir")

    if body.action == "promote":
        promote_candidate(db, t)

    elif body.action == "share":
        t.status = "announced"
        t.decided_by, t.decided_at = user.id, utcnow()

    elif body.action == "dismiss":
        t.status = "dismissed"
        t.decided_by, t.decided_at = user.id, utcnow()

    elif body.action == "pick":
        target = db.get(User, body.assignee_id or "")
        if target is None or target.team_id != user.team_id:
            raise HTTPException(422, "Geçerli bir ekip üyesi seçin")
        if t.is_forcing and t.assignee_id is None:
            t.lead_picked_first = True  # lider, modelin önerisini görmeden seçti
        t.assignee_id = target.id

    elif body.action == "accept":
        if body.assignee_id:
            t.assignee_id = body.assignee_id
        if t.is_forcing and t.assignee_id is None:
            raise HTTPException(409, "Bu görevde önce kendi seçiminizi yapın")
        t.assignee_id = t.assignee_id or t.suggested_assignee_id
        if t.assignee_id is None:
            raise HTTPException(409, "Atanacak kişi yok")
        t.status = "accepted"
        t.decided_by, t.decided_at = user.id, utcnow()

    elif body.action == "reject":
        t.status = "rejected"
        t.reject_reason = body.reason or "not_task"
        t.decided_by, t.decided_at = user.id, utcnow()

    elif body.action == "undo":
        if t.kind == "announcement":
            t.status = "announcement"
        else:
            t.status = "candidate" if t.status == "dismissed" else "suggested"
        t.reject_reason = None
        t.decided_by = t.decided_at = None

    audit.log(db, user.id, f"task.{body.action}", f"task:{t.id}", assignee=t.assignee_id, suggested=t.suggested_assignee_id)
    db.commit()
    users = {u.id: u for u in db.scalars(select(User))}
    return S.task(db, t, users)


@router.get("/{task_id}/source")
def task_source(task_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Personel için sade kaynak görünümü: görevin cümlesi dokümanda nerede, ne isteniyor, neden bu kişi.
    Dokümandaki diğer görevler ve öneriler gösterilmez."""
    t = db.get(Task, task_id)
    if t is None or t.team_id != user.team_id:
        raise HTTPException(404, "Görev bulunamadı")
    doc = db.get(Document, t.document_id) if t.document_id else None
    allowed = user.is_lead or t.assignee_id == user.id or (doc is not None and user.id in (doc.shared_with or []))
    if not allowed:
        raise HTTPException(403, "Bu görevi görme yetkiniz yok")
    users = {u.id: u for u in db.scalars(select(User).where(User.team_id == t.team_id))}
    by = users.get(t.assigned_by or t.decided_by or "")
    who = users.get(t.assignee_id or t.suggested_assignee_id or "")
    return {
        "id": t.id,
        "key": t.key or f"#{t.id}",
        "title": display_title(t),
        "sentence": t.source_quote or t.title,
        "status": t.status,
        "status_label": S.STATUS_LABELS.get(t.status, t.status),
        "assignee": S.user_brief(who),
        "is_mine": t.assignee_id == user.id,
        "assigned_by": by.name if by else None,
        "assigned_at": t.assigned_at.isoformat() if t.assigned_at else None,
        "due": t.due_date.isoformat() if t.due_date else None,
        "est_days": t.est_days,
        "reasons": [r for r in (t.reasons or []) if "lider görev olarak" not in r],
        "load": load_pct(db, who) if who else None,
        "document": None if doc is None else {
            "id": doc.id, "title": doc.title, "doc_type": doc.doc_type, "text": doc.text,
            "uploaded_by": S.user_brief(doc.uploader), "created_at": doc.created_at.isoformat(),
        },
        "start": t.source_start,
        "end": t.source_end,
        "ref": t.source_ref,
    }
