"""Ekip yükü hesabı."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Task, User

ACTIVE_STATUSES = ("accepted", "exported")


def added_days(db: Session, user_id: str, exclude_task_id: int | None = None) -> float:
    q = select(Task).where(Task.assignee_id == user_id, Task.status.in_(ACTIVE_STATUSES))
    return sum(t.est_days for t in db.scalars(q) if t.id != exclude_task_id)


def load_pct(db: Session, user: User, exclude_task_id: int | None = None) -> int:
    cap = get_settings().sprint_capacity_days
    days = user.base_load_days + added_days(db, user.id, exclude_task_id)
    return round(days / cap * 100)


def base_pct(user: User) -> int:
    return round(user.base_load_days / get_settings().sprint_capacity_days * 100)
