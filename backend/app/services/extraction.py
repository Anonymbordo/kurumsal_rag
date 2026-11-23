"""Doküman → görev önerileri.

Akış:
  1. LLM/encoder sağlayıcısı görevleri çıkarır (her biri kaynağına bağlı).
  2. Görev ve ekibin geçmiş işleri aynı embedding uzayına taşınır.
  3. Kişi önerisi: uzmanlık + geçmiş iş + anlamsal benzerlik + yük.
  4. HDBSCAN ile iş alanlarına kümelenir; hiçbir alana girmeyen görev "aykırı"
     sayılır ve güveni bir kademe düşürülür (lider daha dikkatli baksın diye).
"""
import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..llm import get_provider
from ..ml.clustering import cluster
from ..ml.embedder import Embedder, HashingEmbedder
from ..models import Document, Task, User
from .assignment import SemanticMap, suggest

OUTLIER_REASON = "Ekipte benzeri yapılmamış, alışılmadık bir görev"


def _embedder_for(provider) -> tuple[Embedder, bool]:
    """Encoder sağlayıcısının modeli varsa onu kullan; yoksa hafif yedek (anlamsal sinyal zayıf)."""
    emb = getattr(provider, "embedder", None)
    return (emb, True) if emb is not None else (HashingEmbedder(), False)


def _semantic_map(task_vec: np.ndarray, history: list[Task], hist_vecs: np.ndarray) -> SemanticMap:
    out: SemanticMap = {}
    if not history:
        return out
    sims = hist_vecs @ task_vec
    for t, s in zip(history, sims):
        if t.assignee_id and (t.assignee_id not in out or s > out[t.assignee_id][0]):
            out[t.assignee_id] = (float(s), f"{t.key} {t.title}" if t.key else t.title)
    return out


def extract_for_document(db: Session, doc: Document) -> list[Task]:
    provider = get_provider()
    extracted = provider.extract_tasks(doc.text, doc.doc_type)

    # Aynı doküman yeniden işlenirse: karara bağlanmamış eski öneriler ve adaylar silinir,
    # karar verilmiş (onaylanan/reddedilen/aktarılan/elenen) cümleler tekrar önerilmez.
    db.execute(delete(Task).where(Task.document_id == doc.id, Task.status.in_(("suggested", "candidate"))))
    decided = db.scalars(select(Task).where(Task.document_id == doc.id)).all()
    taken = {(t.source_start, t.source_end) for t in decided}
    extracted = [ex for ex in extracted if (ex.source_start, ex.source_end) not in taken]
    next_no = max((t.order_no for t in decided), default=0)

    embedder, semantic_ok = _embedder_for(provider)
    history = [
        t
        for t in db.scalars(
            select(Task).where(Task.team_id == doc.team_id, Task.status.in_(("done", "exported", "accepted")))
        )
        if t.document_id != doc.id
    ]
    hist_texts = [t.title for t in history]
    new_texts = [ex.source_quote or ex.title for ex in extracted]
    hist_vecs = embedder.encode(hist_texts) if hist_texts else np.zeros((0, 1))
    new_vecs = embedder.encode(new_texts) if new_texts else np.zeros((0, 1))

    # İş alanı kümeleri: geçmiş + yeni görevler birlikte. Yalnızca gerçek anlamsal
    # embedding varken (encoder sağlayıcısı) yapılır; kural tabanlı modda yanıltıcı olur.
    all_texts = hist_texts + new_texts
    clusters = None if not semantic_ok else cluster(
        all_texts,
        np.vstack([hist_vecs, new_vecs]) if len(hist_texts) and len(new_texts) else new_vecs,
        get_settings().cluster_min_size,
        exclude_words={u.name.split()[0] for u in db.scalars(select(User))},
    ) if new_texts else None

    tasks: list[Task] = []
    pending: dict[str, float] = {}  # bu dokümanda şimdiye kadar önerilen iş günleri (yük dengeleme)
    for i, ex in enumerate(extracted):
        if ex.candidate:
            # Aktif öğrenme adayı: kişi önerisi lider "görev" derse hesaplanır.
            t = Task(
                document_id=doc.id, team_id=doc.team_id, order_no=next_no + i + 1, title=ex.title,
                detail=ex.detail, tags=ex.tags, est_days=ex.est_days, source_ref=ex.source_ref,
                source_quote=ex.source_quote, source_start=ex.source_start, source_end=ex.source_end,
                detect_score=ex.detect_score, status="candidate", confidence=1, reasons=[],
            )
            db.add(t)
            tasks.append(t)
            continue
        semantic = _semantic_map(new_vecs[i], history, hist_vecs) if semantic_ok else None
        s = suggest(db, doc.team_id, ex.tags, semantic, text=ex.source_quote, pending_days=pending)
        if s.assignee_id:
            pending[s.assignee_id] = pending.get(s.assignee_id, 0.0) + ex.est_days
        confidence, reasons = s.confidence, list(s.reasons)

        workstream, outlier = None, False
        if clusters is not None and len(clusters.labels) == len(all_texts):
            j = len(hist_texts) + i
            lab = int(clusters.labels[j])
            outlier = bool(clusters.outliers[j])
            workstream = clusters.names.get(lab)
            if outlier:
                confidence = max(1, confidence - 1)
                reasons.append(OUTLIER_REASON)

        t = Task(
            document_id=doc.id,
            team_id=doc.team_id,
            order_no=next_no + i + 1,
            title=ex.title,
            detail=ex.detail,
            tags=ex.tags,
            est_days=ex.est_days,
            source_ref=ex.source_ref,
            source_quote=ex.source_quote,
            source_start=ex.source_start,
            source_end=ex.source_end,
            detect_score=ex.detect_score,
            workstream=workstream,
            is_outlier=outlier,
            suggested_assignee_id=s.assignee_id,
            alt_assignee_id=s.alt_assignee_id,
            confidence=confidence,
            reasons=reasons,
            status="suggested",
        )
        db.add(t)
        tasks.append(t)
    db.flush()
    return tasks


def promote_candidate(db: Session, t: Task) -> None:
    """Lider aday cümleye "görev" dedi: kişi önerisini şimdi hesapla."""
    s = suggest(db, t.team_id, t.tags, text=t.source_quote)
    t.status = "suggested"
    t.suggested_assignee_id, t.alt_assignee_id = s.assignee_id, s.alt_assignee_id
    t.confidence, t.reasons = s.confidence, s.reasons + ["Model emin değildi; lider görev olarak işaretledi"]
