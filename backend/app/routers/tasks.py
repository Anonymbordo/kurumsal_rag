from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import serialize as S
from ..db import get_db
from ..deps import require_lead
from ..models import Task, User
from ..services import audit
from ..services.extraction import promote_candidate
from ..timeutil import utcnow

router = APIRouter(prefix="/api/tasks", tags=["görevler"])


class Decision(BaseModel):
    action: Literal["pick", "accept", "reject", "undo", "promote", "dismiss"]
    assignee_id: str | None = None
    reason: Literal["not_task", "not_now"] | None = None  # reject için


@router.post("/{task_id}/decision")
def decide(task_id: int, body: Decision, user: User = Depends(require_lead), db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if t is None or t.team_id != user.team_id:
        raise HTTPException(404, "Görev bulunamadı")
    if t.status in ("exported", "done"):
        raise HTTPException(409, "Aktarılmış görev bu ekrandan değiştirilemez")

    if t.status in ("candidate", "dismissed") and body.action not in ("promote", "dismiss", "undo"):
        raise HTTPException(409, "Önce bu cümlenin görev olup olmadığına karar verin")

    if body.action == "promote":
        promote_candidate(db, t)

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
        t.status = "candidate" if t.status == "dismissed" else "suggested"
        t.reject_reason = None
        t.decided_by = t.decided_at = None

    audit.log(db, user.id, f"task.{body.action}", f"task:{t.id}", assignee=t.assignee_id, suggested=t.suggested_assignee_id)
    db.commit()
    users = {u.id: u for u in db.scalars(select(User))}
    return S.task(db, t, users)
