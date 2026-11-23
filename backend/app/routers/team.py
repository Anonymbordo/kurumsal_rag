from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from .. import serialize as S
from ..deps import current_user, require_lead
from ..models import Conversation, Document, Task, User
from ..services import audit
from ..services.people import skills_for_role
from ..services.team import create_member, has_tasks
from ..services.assignment import CAPACITY_LIMIT_PCT, TAG_LABELS
from ..services.load import base_pct, load_pct

router = APIRouter(prefix="/api", tags=["ekip"])

CONF_LABELS = {3: "Yüksek güven", 2: "Orta güven", 1: "Düşük güven"}


@router.get("/team/load")
def team_load(user: User = Depends(current_user), db: Session = Depends(get_db)):
    members = db.scalars(select(User).where(User.team_id == user.team_id, User.is_lead.is_(False)).order_by(User.name))
    out = []
    for u in members:
        added = db.scalars(
            select(Task).where(Task.assignee_id == u.id, Task.status.in_(("accepted", "exported")))
        ).all()
        out.append(
            {
                "id": u.id,
                "name": u.name,
                "role": u.role,
                "before": base_pct(u),
                "after": load_pct(db, u),
                "new_tasks": len(added),
            }
        )
    return {"limit": CAPACITY_LIMIT_PCT, "members": out}


def _decided(db: Session, team_id: str) -> list[Task]:
    q = select(Task).where(
        Task.team_id == team_id,
        Task.suggested_assignee_id.is_not(None),
        Task.decided_by.is_not(None),
        Task.status.in_(("accepted", "exported", "done")),
    )
    return list(db.scalars(q))


@router.get("/stats/accuracy")
def accuracy(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Liderin öneriyi değiştirmeden onayladığı oran, güven seviyesine göre."""
    rows = []
    tasks = _decided(db, user.team_id)
    for level in (3, 2, 1):
        group = [t for t in tasks if t.confidence == level]
        same = sum(1 for t in group if t.assignee_id == t.suggested_assignee_id)
        rows.append(
            {
                "level": level,
                "label": CONF_LABELS[level],
                "total": len(group),
                "unchanged_pct": round(same / len(group) * 100) if group else None,
            }
        )
    return rows


@router.get("/stats/corrections")
def corrections(user: User = Depends(current_user), db: Session = Depends(get_db)):
    c: Counter[str] = Counter()
    for t in _decided(db, user.team_id):
        if t.assignee_id != t.suggested_assignee_id:
            for tag in t.tags:
                if tag != "general":
                    c[TAG_LABELS.get(tag, tag)] += 1
    return [{"label": k, "count": v} for k, v in c.most_common(5)]


class NewMember(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    role: str = Field(default="", max_length=120)
    skills: list[str] | None = None  # boşsa rolden tahmin edilir
    base_load_days: float = 0.0
    is_lead: bool = False


class MemberPatch(BaseModel):
    role: str | None = None
    skills: list[str] | None = None
    base_load_days: float | None = None


@router.get("/team/skills")
def skill_options():
    return [{"id": k, "label": v} for k, v in TAG_LABELS.items() if k != "general"]


@router.post("/team/members")
def add_member(body: NewMember, user: User = Depends(require_lead), db: Session = Depends(get_db)):
    skills = body.skills if body.skills is not None else skills_for_role(body.role)
    skills = [s for s in skills if s in TAG_LABELS and s != "general"]
    u = create_member(db, user.team_id, body.name, body.role, skills, body.base_load_days, body.is_lead)
    audit.log(db, user.id, "team.add", f"user:{u.id}", name=u.name)
    db.commit()
    return S.user_full(db, u)


@router.patch("/team/members/{uid}")
def update_member(uid: str, body: MemberPatch, user: User = Depends(require_lead), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if u is None or u.team_id != user.team_id:
        raise HTTPException(404, "Ekip üyesi bulunamadı")
    if body.role is not None:
        u.role = body.role.strip() or u.role
    if body.skills is not None:
        u.skills = sorted({s for s in body.skills if s in TAG_LABELS and s != "general"})
    if body.base_load_days is not None:
        u.base_load_days = max(0.0, body.base_load_days)
    audit.log(db, user.id, "team.update", f"user:{u.id}")
    db.commit()
    return S.user_full(db, u)


@router.delete("/team/members/{uid}")
def remove_member(uid: str, user: User = Depends(require_lead), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if u is None or u.team_id != user.team_id:
        raise HTTPException(404, "Ekip üyesi bulunamadı")
    if u.id == user.id:
        raise HTTPException(409, "Kendinizi ekipten çıkaramazsınız")
    if (
        has_tasks(db, u.id)
        or db.scalar(select(Document.id).where(Document.uploaded_by == u.id).limit(1))
        or db.scalar(select(Conversation.id).where(Conversation.user_id == u.id).limit(1))
    ):
        raise HTTPException(409, "Bu kişinin görev geçmişi var; denetim kaydı için silinemez")
    db.delete(u)
    audit.log(db, user.id, "team.remove", f"user:{uid}")
    db.commit()
    return {"removed": uid}
