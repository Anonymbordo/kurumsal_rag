"""Ekip üyesi ekleme/çıkarma.

Kurum kurulumunda ekip listesi LDAP / Active Directory'den eşitlenir; bu servis
o eşitleme için de aynı giriş noktasıdır.
"""
import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import Task, User

_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.translate(_TR).lower()).strip("-")
    return s[:36] or "kisi"


def create_member(
    db: Session,
    team_id: str,
    name: str,
    role: str,
    skills: list[str],
    base_load_days: float = 0.0,
    is_lead: bool = False,
) -> User:
    base = _slug(name)
    uid, n = base, 2
    while db.get(User, uid) is not None:
        uid, n = f"{base}-{n}", n + 1
    u = User(
        id=uid, name=" ".join(name.split()), role=role.strip() or "Ekip üyesi", team_id=team_id,
        is_lead=is_lead, skills=sorted(set(skills)), base_load_days=max(0.0, base_load_days),
    )
    db.add(u)
    db.flush()
    return u


def has_tasks(db: Session, user_id: str) -> bool:
    q = select(Task.id).where(
        or_(Task.assignee_id == user_id, Task.suggested_assignee_id == user_id, Task.alt_assignee_id == user_id,
            Task.decided_by == user_id, Task.assigned_by == user_id)
    ).limit(1)
    return db.scalar(q) is not None
