"""Toplantılar: oluştur, katıl (Jitsi), kaydı parça parça yükle, bitir, raporu gör."""
import os
import re
import secrets

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import serialize as S
from ..config import get_settings
from ..db import get_db
from ..deps import current_user
from ..models import Meeting, MeetingRecording, User
from ..services import audit
from ..services import meetings as svc
from ..services.meetings import fmt_ts
from ..timeutil import utcnow

router = APIRouter(prefix="/api/meetings", tags=["toplantılar"])

MAX_CHUNK = 8 * 1024 * 1024
MAX_UPLOAD = 300 * 1024 * 1024
AUDIO_TYPES = {"audio/webm", "audio/ogg", "audio/mpeg", "audio/mp4", "audio/wav", "audio/x-wav", "audio/x-m4a",
               "video/mp4", "video/webm", "application/octet-stream"}


class NewMeeting(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    participants: list[str] = []


def _get(db: Session, mid: int, user: User) -> Meeting:
    m = db.get(Meeting, mid)
    if m is None or m.team_id != user.team_id:
        raise HTTPException(404, "Toplantı bulunamadı")
    if not (user.is_lead or user.id == m.created_by or user.id in (m.participants or [])):
        raise HTTPException(403, "Bu toplantının katılımcısı değilsiniz")
    return m


def _out(db: Session, m: Meeting, detail: bool = False) -> dict:
    users = {u.id: u for u in db.scalars(select(User).where(User.team_id == m.team_id))}
    out = {
        "id": m.id,
        "title": m.title,
        "status": m.status,
        "progress": m.progress,
        "error": m.error,
        "created_by": S.user_brief(users.get(m.created_by)),
        "participants": [S.user_brief(users[u]) for u in (m.participants or []) if u in users],
        "started_at": m.started_at.isoformat(),
        "ended_at": m.ended_at.isoformat() if m.ended_at else None,
        "document_id": m.document_id,
    }
    if detail:
        s = get_settings()
        recs = db.scalars(select(MeetingRecording).where(MeetingRecording.meeting_id == m.id)).all()
        out |= {
            "room": m.room,
            "jitsi_domain": s.jitsi_domain,
            "report": m.report,
            "transcript": [{**u, "ts": fmt_ts(u["start"])} for u in (m.transcript or [])],
            "recordings": [
                {"id": r.id, "speaker": r.speaker, "user_id": r.user_id, "chunks": r.chunks, "bytes": r.bytes}
                for r in recs
            ],
        }
    return out


@router.get("")
def list_meetings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ms = db.scalars(select(Meeting).where(Meeting.team_id == user.team_id).order_by(Meeting.started_at.desc())).all()
    visible = [m for m in ms if user.is_lead or user.id == m.created_by or user.id in (m.participants or [])]
    return [_out(db, m) for m in visible]


@router.post("")
def create(body: NewMeeting, user: User = Depends(current_user), db: Session = Depends(get_db)):
    team = set(db.scalars(select(User.id).where(User.team_id == user.team_id)))
    parts = sorted({p for p in body.participants if p in team} | {user.id})
    slug = re.sub(r"[^a-z0-9]+", "", body.title.lower().translate(str.maketrans("çğıöşü", "cgiosu")))[:20]
    m = Meeting(team_id=user.team_id, title=body.title.strip(), created_by=user.id, participants=parts,
                room=f"ga-{slug or 'toplanti'}-{secrets.token_hex(6)}")
    db.add(m)
    audit.log(db, user.id, "meeting.create", f"meeting:{m.title}", participants=parts)
    db.commit()
    return _out(db, m, detail=True)


@router.get("/{mid}")
def get_meeting(mid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _out(db, _get(db, mid, user), detail=True)


@router.post("/{mid}/recordings")
def start_recording(mid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Bu katılımcının yeni bir kayıt oturumunu başlatır (tarayıcıda 'Kaydı başlat')."""
    m = _get(db, mid, user)
    if m.status != "live":
        raise HTTPException(409, "Toplantı bitti; yeni kayıt başlatılamaz")
    offset = (utcnow() - m.started_at).total_seconds()
    r = MeetingRecording(meeting_id=m.id, user_id=user.id, speaker=user.name, offset_s=max(0.0, offset), path="")
    db.add(r)
    db.flush()
    r.path = os.path.join(svc.audio_dir(m.id), f"{r.id}_{user.id}.webm")
    db.commit()
    return {"id": r.id, "offset_s": r.offset_s}


@router.post("/recordings/{rid}/chunks")
async def upload_chunk(rid: int, seq: int, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Kayıt parçası (MediaRecorder çıktısı). Parçalar sırayla aynı dosyaya eklenir."""
    r = db.get(MeetingRecording, rid)
    if r is None or r.user_id != user.id:
        raise HTTPException(404, "Kayıt bulunamadı")
    m = db.get(Meeting, r.meeting_id)
    if m.status not in ("live",) and not (m.status == "processing" and m.progress == "Sırada…"):
        raise HTTPException(409, "Toplantı işlenmeye başladı; kayıt kapandı")
    if seq != r.chunks:
        raise HTTPException(409, f"Beklenen parça {r.chunks}, gelen {seq}")
    data = await request.body()
    if len(data) > MAX_CHUNK:
        raise HTTPException(413, "Parça çok büyük")
    with open(r.path, "ab") as f:
        f.write(data)
    r.chunks += 1
    r.bytes += len(data)
    db.commit()
    return {"chunks": r.chunks}


@router.post("/{mid}/audio")
async def upload_audio(mid: int, file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Hazır bir kaydı yükle (ör. odadaki tek cihazın kaydı). Konuşmacı yükleyen kişi sayılır."""
    m = _get(db, mid, user)
    if m.status != "live":
        raise HTTPException(409, "Toplantı bitti")
    if file.content_type and file.content_type not in AUDIO_TYPES:
        raise HTTPException(415, "Desteklenmeyen dosya türü")
    ext = os.path.splitext(file.filename or "")[1].lower()[:6] or ".webm"
    r = MeetingRecording(meeting_id=m.id, user_id=user.id, speaker=user.name, offset_s=0.0, path="",
                         mime=file.content_type or "")
    db.add(r)
    db.flush()
    r.path = os.path.join(svc.audio_dir(m.id), f"{r.id}_{user.id}_upload{ext}")
    size = 0
    with open(r.path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD:
                raise HTTPException(413, "Dosya 300 MB'tan büyük")
            f.write(chunk)
    r.chunks, r.bytes = 1, size
    db.commit()
    return {"id": r.id, "bytes": size}


@router.post("/{mid}/end")
def end_meeting(mid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = _get(db, mid, user)
    if not (user.is_lead or user.id == m.created_by):
        raise HTTPException(403, "Toplantıyı yalnızca düzenleyen ya da takım lideri bitirebilir")
    if m.status != "live":
        raise HTTPException(409, "Toplantı zaten bitti")
    audit.log(db, user.id, "meeting.end", f"meeting:{m.id}")
    svc.finish(db, m)
    return _out(db, m, detail=True)


@router.post("/{mid}/retry")
def retry(mid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """İşleme hata verdiyse (ör. whisper kurulu değildi) yeniden dene."""
    m = _get(db, mid, user)
    if m.status != "failed":
        raise HTTPException(409, "Yalnızca hata veren toplantı yeniden işlenebilir")
    m.error = ""
    svc.finish(db, m)
    return _out(db, m, detail=True)
