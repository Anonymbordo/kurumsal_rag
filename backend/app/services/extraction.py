"""Doküman → görev önerileri."""
from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..llm import get_provider
from ..models import Document, Task
from .assignment import suggest


def extract_for_document(db: Session, doc: Document) -> list[Task]:
    provider = get_provider()
    extracted = provider.extract_tasks(doc.text, doc.doc_type)

    # Aynı doküman yeniden işlenirse karara bağlanmamış eski öneriler silinir.
    db.execute(delete(Task).where(Task.document_id == doc.id, Task.status == "suggested"))

    tasks: list[Task] = []
    for i, ex in enumerate(extracted, start=1):
        s = suggest(db, doc.team_id, ex.tags)
        t = Task(
            document_id=doc.id,
            team_id=doc.team_id,
            order_no=i,
            title=ex.title,
            detail=ex.detail,
            tags=ex.tags,
            est_days=ex.est_days,
            source_ref=ex.source_ref,
            source_quote=ex.source_quote,
            source_start=ex.source_start,
            source_end=ex.source_end,
            suggested_assignee_id=s.assignee_id,
            alt_assignee_id=s.alt_assignee_id,
            confidence=s.confidence,
            reasons=s.reasons,
            status="suggested",
        )
        db.add(t)
        tasks.append(t)
    db.flush()
    return tasks
