"""Toplantı → döküm → rapor → görev önerileri.

  1. Her katılımcının kaydı ayrı ayrı yazıya dökülür (faster-whisper, CPU).
     Konuşmacı, kaydın sahibidir: diarization modeline gerek yok.
  2. Tüm parçalar toplantı zamanına göre sıralanır, aynı kişinin ardışık sözleri birleşir.
  3. Döküm bir doküman olarak kaydedilir ("Ayşe Kaya: ..." satırları) ve mevcut görev çıkarma
     hattından geçer (encoder + probe + kümeleme + kişi önerisi). Konuşan kişinin kendi üstlendiği
     işler ona önerilir.
  4. Rapor: decoder bağlıysa özet ve kararlar decoder'dan; görev listesi HER ZAMAN bizim hattan
     (kaynaklı, lider onayına bağlı). Decoder yoksa rapor dökümden derlenir.
"""
import os
import threading
import time
import traceback
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import SessionLocal
from ..llm import ChatTurn
from ..llm.decoder import DecoderUnavailable, get_decoder
from ..models import Document, Meeting, MeetingRecording, Task, User
from ..timeutil import utcnow
from .extraction import extract_for_document
from .transcribe import get_transcriber

MERGE_GAP_S = 4.0  # aynı kişinin bu kadar yakın sözleri tek paragraf olur


def audio_dir(meeting_id: int) -> str:
    d = os.path.join(get_settings().data_dir, "meetings", str(meeting_id))
    os.makedirs(d, exist_ok=True)
    return d


def fmt_ts(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60:02d}:{sec % 60:02d}"


def merge_segments(segs: list[dict]) -> list[dict]:
    """Zamana göre sırala; aynı konuşmacının ardışık parçalarını birleştir."""
    out: list[dict] = []
    for s in sorted(segs, key=lambda x: x["start"]):
        if out and out[-1]["speaker"] == s["speaker"] and s["start"] - out[-1]["end"] <= MERGE_GAP_S:
            out[-1]["end"] = max(out[-1]["end"], s["end"])
            out[-1]["text"] = (out[-1]["text"] + " " + s["text"]).strip()
        else:
            out.append(dict(s))
    return out


def transcript_text(m: Meeting) -> str:
    """Görev çıkarma için doküman metni: başlık + "Konuşmacı: söz" satırları."""
    lines = [f"{m.title} (toplantı dökümü)"]
    for u in m.transcript:
        text = u["text"].strip()
        if text and text[-1] not in ".!?":
            text += "."
        lines.append(f"{u['speaker']}: {text}")
    return "\n".join(lines)


# --- Rapor ----------------------------------------------------------------
NOTES_PROMPT = """Aşağıda bir iş toplantısının dökümünden bir bölüm var. Bu bölümdeki önemli bilgileri, alınan kararları ve kimin ne yapacağını Türkçe, kısa maddeler halinde çıkar. Dökümde olmayan hiçbir şey ekleme. Kişi adlarını aynen koru.

DÖKÜM:
{chunk}"""

REPORT_PROMPT = """Aşağıdaki notlar "{title}" toplantısından çıkarıldı. Bunlardan Türkçe bir toplantı raporu yaz.
Yalnızca notlardaki bilgiyi kullan, uydurma. Şu başlıkları kullan ve başka başlık ekleme:
## Özet
(2-4 cümle)
## Alınan kararlar
(madde madde; yoksa "Karar alınmadı.")
## Açık konular
(madde madde; yoksa "Yok.")

NOTLAR:
{notes}"""

CHUNK_CHARS = 3500


def _chunks(lines: list[str], size: int = CHUNK_CHARS) -> list[str]:
    out, cur = [], ""
    for ln in lines:
        if cur and len(cur) + len(ln) > size:
            out.append(cur)
            cur = ""
        cur += ln + "\n"
    if cur:
        out.append(cur)
    return out


def llm_summary(m: Meeting, on_progress=lambda s: None) -> str | None:
    """Uzun dökümler için iki aşama (map-reduce): parça parça not çıkar, sonra raporu yaz."""
    dec = get_decoder()
    if dec is None:
        return None
    lines = [f"[{fmt_ts(u['start'])}] {u['speaker']}: {u['text']}" for u in m.transcript]
    parts = _chunks(lines)
    try:
        notes = []
        for i, chunk in enumerate(parts, 1):
            on_progress(f"Rapor yazılıyor: döküm bölümü {i}/{len(parts)}")
            g = dec.generate("Sen bir toplantı not tutucususun.", [ChatTurn("user", NOTES_PROMPT.format(chunk=chunk))],
                             max_tokens=350, num_ctx=4096)
            notes.append(g.text)
        on_progress("Rapor yazılıyor: son düzenleme")
        g = dec.generate(
            "Sen bir toplantı raporu yazarısın.",
            [ChatTurn("user", REPORT_PROMPT.format(title=m.title, notes="\n".join(notes)))],
            max_tokens=500, num_ctx=4096,
        )
        return g.text.strip() + f"\n\n_Rapor yerel dil modeliyle ({dec.model}) dökümden üretildi; kararları dökümle karşılaştırın._"
    except DecoderUnavailable:
        return None


def build_report(db: Session, m: Meeting, summary: str | None, tasks: list[Task]) -> str:
    users = {u.id: u for u in db.scalars(select(User))}
    dur = (m.ended_at - m.started_at) if m.ended_at else timedelta()
    talk: dict[str, float] = {}
    for u in m.transcript:
        talk[u["speaker"]] = talk.get(u["speaker"], 0.0) + max(0.0, u["end"] - u["start"])

    out = [f"# {m.title}", f"Tarih: {m.started_at:%d.%m.%Y %H:%M} UTC · Süre: {int(dur.total_seconds() // 60)} dk"]
    if talk:
        out.append("Konuşanlar: " + ", ".join(f"{k} ({int(v // 60)} dk {int(v % 60)} sn)" for k, v in sorted(talk.items(), key=lambda x: -x[1])))
    out.append("")
    out.append(summary or "## Özet\nDil modeli bağlı olmadığı için özet üretilmedi. Döküm ve görev önerileri aşağıda.")
    out.append("\n## Görev önerileri (lider onayı bekliyor)")
    real = [t for t in tasks if t.kind != "announcement" and t.status == "suggested"]
    if not real:
        out.append("Dökümde görev bulunamadı.")
    for t in real:
        who = users.get(t.suggested_assignee_id or "")
        out.append(f"- {t.title} → **{who.name if who else 'atanmadı'}** ({t.source_ref})")
    ann = [t for t in tasks if t.kind == "announcement"]
    if ann:
        out.append("\n## Duyurular")
        out += [f"- {t.source_quote}" for t in ann]
    return "\n".join(out)


# --- İşleme ---------------------------------------------------------------
def _set(db: Session, m: Meeting, progress: str) -> None:
    m.progress = progress
    db.commit()


def process(meeting_id: int) -> None:
    """Toplantı bittikten sonra arka planda çalışır."""
    with SessionLocal() as db:
        m = db.get(Meeting, meeting_id)
        if m is None:
            return
        try:
            recs = db.scalars(select(MeetingRecording).where(MeetingRecording.meeting_id == m.id, MeetingRecording.bytes > 0)).all()
            if not recs:
                raise RuntimeError("Toplantıda hiç ses kaydı yok. Katılımcılar 'Kaydı başlat' demeli.")
            _set(db, m, "Konuşma tanıma modeli yükleniyor…")
            asr = get_transcriber()
            segs: list[dict] = []
            for i, r in enumerate(recs, 1):
                _set(db, m, f"Yazıya dökülüyor: {r.speaker} ({i}/{len(recs)})")
                for s in asr.transcribe(r.path):
                    segs.append({"user_id": r.user_id, "speaker": r.speaker,
                                 "start": round(r.offset_s + s.start, 2), "end": round(r.offset_s + s.end, 2), "text": s.text})
            m.transcript = merge_segments(segs)
            if not m.transcript:
                raise RuntimeError("Kayıtlarda anlaşılır konuşma bulunamadı.")

            _set(db, m, "Görevler çıkarılıyor…")
            doc = Document(title=f"{m.title} (toplantı)", doc_type="meeting", text=transcript_text(m),
                           uploaded_by=m.created_by, team_id=m.team_id, shared_with=list(m.participants))
            db.add(doc)
            db.flush()
            m.document_id = doc.id
            tasks = extract_for_document(db, doc)
            db.commit()

            summary = llm_summary(m, lambda p: _set(db, m, p))
            m.report = build_report(db, m, summary, tasks)
            m.status, m.progress = "done", ""
            db.commit()
            if not get_settings().keep_audio:
                for r in recs:
                    try:
                        os.remove(r.path)
                    except OSError:
                        pass
        except Exception as e:  # noqa: BLE001 — kullanıcıya gösterilecek
            db.rollback()
            m = db.get(Meeting, meeting_id)
            m.status, m.progress = "failed", ""
            m.error = f"{e}" if str(e) else traceback.format_exc(limit=2)
            db.commit()


GRACE_S = 8.0  # son kayıt parçalarının yüklenmesi için bekleme


def start_processing(meeting_id: int) -> None:
    def run():
        time.sleep(GRACE_S)
        process(meeting_id)

    threading.Thread(target=run, daemon=True).start()


def finish(db: Session, m: Meeting) -> None:
    m.status, m.ended_at, m.progress = "processing", utcnow(), "Sırada…"
    db.commit()
    start_processing(m.id)
