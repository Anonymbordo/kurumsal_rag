from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import serialize as S
from ..config import get_settings
from ..db import get_db
from ..deps import current_user
from ..models import Group, Task, User

router = APIRouter(prefix="/api", tags=["kurum"])


@router.get("/org")
def org():
    s = get_settings()
    return {
        "name": s.org_name,
        "accent": s.org_accent,
        "logo_url": s.org_logo_url or None,
        "model_label": s.llm_model_label,
        "llm_provider": s.llm_provider,
    }


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return S.user_full(db, user)


@router.get("/users")
def users(db: Session = Depends(get_db)):
    """Geliştirme için kullanıcı değiştirme listesi."""
    return [S.user_full(db, u) for u in db.scalars(select(User).order_by(User.is_lead.desc(), User.name))]


@router.get("/team/members")
def team_members(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(User).where(User.team_id == user.team_id, User.is_lead.is_(False)).order_by(User.name)
    return [S.user_full(db, u) for u in db.scalars(q)]


@router.get("/groups")
def groups(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [S.group(g) for g in db.scalars(select(Group)) if user.id in g.member_ids]


@router.get("/tasks/mine")
def my_tasks(user: User = Depends(current_user), db: Session = Depends(get_db)):
    users_map = {u.id: u for u in db.scalars(select(User))}
    q = select(Task).where(Task.assignee_id == user.id, Task.status.in_(("exported", "done")))
    tasks = sorted(db.scalars(q), key=lambda t: (t.status == "done", -(t.id)))
    return [S.task(db, t, users_map) for t in tasks]
