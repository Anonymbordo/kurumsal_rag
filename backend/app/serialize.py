"""Model → JSON dönüşümleri."""
from sqlalchemy.orm import Session

from .models import Conversation, Document, Group, Message, Task, User
from .services.load import load_pct

STATUS_LABELS = {
    "suggested": "Karar bekliyor",
    "accepted": "Onaylandı",
    "rejected": "Reddedildi",
    "exported": "Devam ediyor",
    "done": "Tamamlandı",
}


def user_brief(u: User | None) -> dict | None:
    if u is None:
        return None
    return {"id": u.id, "name": u.name, "initials": u.initials, "role": u.role}


def user_full(db: Session, u: User) -> dict:
    return {
        **user_brief(u),
        "team_id": u.team_id,
        "team_name": u.team.name if u.team else "",
        "is_lead": u.is_lead,
        "skills": u.skills,
        "load": load_pct(db, u),
    }


def task(db: Session, t: Task, users: dict[str, User]) -> dict:
    def person(uid: str | None) -> dict | None:
        u = users.get(uid) if uid else None
        if u is None:
            return None
        return {**user_brief(u), "load": load_pct(db, u, exclude_task_id=t.id)}

    return {
        "id": t.id,
        "key": t.key,
        "order_no": t.order_no,
        "document_id": t.document_id,
        "title": t.title,
        "detail": t.detail,
        "tags": t.tags,
        "est_days": t.est_days,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "source": {"ref": t.source_ref, "quote": t.source_quote, "start": t.source_start, "end": t.source_end},
        "suggested": person(t.suggested_assignee_id),
        "alternative": person(t.alt_assignee_id),
        "assignee": person(t.assignee_id),
        "confidence": t.confidence,
        "forcing": t.is_forcing,
        "reasons": t.reasons,
        "detect_score": t.detect_score,
        "workstream": t.workstream,
        "is_outlier": t.is_outlier,
        "status": t.status,
        "status_label": STATUS_LABELS.get(t.status, t.status),
        "lead_picked_first": t.lead_picked_first,
    }


def document(d: Document, with_text: bool = False) -> dict:
    out = {
        "id": d.id,
        "title": d.title,
        "doc_type": d.doc_type,
        "sprint": d.sprint,
        "uploaded_by": user_brief(d.uploader),
        "related_task_key": d.related_task_key,
        "created_at": d.created_at.isoformat(),
        "char_count": len(d.text),
    }
    if with_text:
        out["text"] = d.text
    return out


def group(g: Group) -> dict:
    return {"id": g.id, "name": g.name, "short": g.short, "color": g.color, "member_count": len(g.member_ids)}


def conversation(c: Conversation) -> dict:
    return {"id": c.id, "title": c.title, "updated_at": c.updated_at.isoformat()}


def message(m: Message) -> dict:
    return {
        "id": m.id,
        "role": m.role,
        "text": m.text,
        "blocks": m.blocks,
        "sources": m.sources,
        "created_at": m.created_at.isoformat(),
    }
