from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Task, User
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
