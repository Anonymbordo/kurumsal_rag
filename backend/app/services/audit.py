from sqlalchemy.orm import Session

from ..models import AuditLog


def log(db: Session, user_id: str, action: str, target: str, **detail) -> None:
    db.add(AuditLog(user_id=user_id, action=action, target=target, detail=detail))
