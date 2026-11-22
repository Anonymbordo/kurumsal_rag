from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import serialize as S
from ..db import get_db
from ..deps import current_user, require_lead
from ..models import Document, Task, User
from ..services import audit
from ..services.documents import UnsupportedFile, extract_text
from ..services.extraction import extract_for_document
from ..timeutil import utcnow

router = APIRouter(prefix="/api/documents", tags=["dokümanlar"])

MAX_BYTES = 10 * 1024 * 1024


def _get_doc(db: Session, doc_id: int, user: User) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "Doküman bulunamadı")
    if doc.team_id != user.team_id and user.id not in (doc.shared_with or []):
        raise HTTPException(403, "Bu dokümana erişiminiz yok")
    return doc


def _users(db: Session) -> dict[str, User]:
    return {u.id: u for u in db.scalars(select(User))}


@router.post("")
async def upload(
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    title: str | None = Form(default=None),
    doc_type: str = Form(default="meeting"),
    sprint: str = Form(default=""),
    user: User = Depends(require_lead),
    db: Session = Depends(get_db),
):
    if file is not None:
        data = await file.read()
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "Dosya 10 MB sınırını aşıyor")
        try:
            body = extract_text(file.filename or "", data)
        except UnsupportedFile as e:
            raise HTTPException(415, str(e)) from e
        name = title or (file.filename or "Doküman").rsplit(".", 1)[0]
    elif text:
        body, name = text, title or "Yapıştırılan metin"
    else:
        raise HTTPException(400, "Dosya ya da metin gönderin")
    if not body.strip():
        raise HTTPException(422, "Dokümandan metin okunamadı")

    doc = Document(title=name, doc_type=doc_type, sprint=sprint, text=body, uploaded_by=user.id, team_id=user.team_id)
    db.add(doc)
    db.flush()
    audit.log(db, user.id, "document.upload", f"document:{doc.id}", title=name)
    db.commit()
    return S.document(doc)


@router.get("/shared")
def shared_with_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    docs = [d for d in db.scalars(select(Document).order_by(Document.created_at.desc())) if user.id in (d.shared_with or [])]
    return [S.document(d) for d in docs]


@router.get("/{doc_id}")
def get_document(doc_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return S.document(_get_doc(db, doc_id, user), with_text=True)


@router.post("/{doc_id}/extract")
def extract(doc_id: int, user: User = Depends(require_lead), db: Session = Depends(get_db)):
    doc = _get_doc(db, doc_id, user)
    tasks = extract_for_document(db, doc)
    audit.log(db, user.id, "document.extract", f"document:{doc.id}", count=len(tasks))
    db.commit()
    users = _users(db)
    return [S.task(db, t, users) for t in db.scalars(select(Task).where(Task.document_id == doc.id).order_by(Task.order_no))]


@router.get("/{doc_id}/tasks")
def document_tasks(doc_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = _get_doc(db, doc_id, user)
    users = _users(db)
    return [S.task(db, t, users) for t in db.scalars(select(Task).where(Task.document_id == doc.id).order_by(Task.order_no))]


def _next_key(db: Session, prefix: str) -> str:
    nums = [
        int(k.split("-")[1])
        for k in db.scalars(select(Task.key).where(Task.key.like(f"{prefix}-%")))
        if k and k.split("-")[1].isdigit()
    ]
    return f"{prefix}-{(max(nums) if nums else 0) + 1}"


@router.post("/{doc_id}/export")
def export(doc_id: int, user: User = Depends(require_lead), db: Session = Depends(get_db)):
    """Onaylanan görevleri iş takip sistemine aktarır.

    Şimdilik görevleri uygulama içinde 'exported' yapar ve anahtar üretir.
    Gerçek Jira / Azure DevOps entegrasyonu buraya bağlanacak.
    """
    doc = _get_doc(db, doc_id, user)
    tasks = db.scalars(select(Task).where(Task.document_id == doc.id, Task.status == "accepted")).all()
    prefix = user.team.key_prefix
    now = utcnow()
    for t in tasks:
        t.key = _next_key(db, prefix)
        t.status = "exported"
        t.assigned_by = user.id
        t.assigned_at = now
        t.due_date = t.due_date or (date.today() + timedelta(days=max(3, round(t.est_days * 2))))
        db.flush()
    if tasks:
        assignees = {t.assignee_id for t in tasks if t.assignee_id}
        doc.shared_with = sorted(set(doc.shared_with or []) | assignees)
    audit.log(db, user.id, "document.export", f"document:{doc.id}", keys=[t.key for t in tasks])
    db.commit()
    return {"exported": [{"id": t.id, "key": t.key} for t in tasks]}
