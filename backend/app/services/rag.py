"""Sohbet için RAG: encoder ilgili kayıtları bulur, decoder yalnızca onlara bakarak cevap yazar.

Kayıt türleri (hepsi kullanıcının görmeye yetkili olduğu veriler):
  - Kullanıcıya atanmış aktif görevler (cümlenin tamamı, dokümandaki bağlamı, gerekçeler, teslim)
  - Görevlerinin geldiği ve kendisiyle paylaşılan dokümanlardaki cümleler

Her kayıt [K1], [K2]... diye numaralanır; decoder kullandığı kaydı köşeli parantezle belirtir,
arayüz bu numaraları kaynak etiketlerine çevirir.
"""
import re
from dataclasses import dataclass
from datetime import date

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..llm import ChatTurn, get_provider
from ..llm.decoder import DecoderUnavailable, Generation, OllamaDecoder
from ..llm.text import split_sentences
from ..ml.embedder import HashingEmbedder
from ..models import Document, Message, Task, User

CITE = re.compile(r"\[K(\d+)\]")


@dataclass
class Record:
    text: str
    label: str  # arayüzde gösterilecek kaynak adı


def _embedder():
    return getattr(get_provider(), "embedder", None) or HashingEmbedder()


def doc_context(doc: Document | None, start: int, end: int, n: int = 1) -> tuple[str, str]:
    """Görev cümlesinden önceki ve sonraki n cümle."""
    if doc is None or start < 0:
        return "", ""
    sents = split_sentences(doc.text, min_len=5)
    before = [s.text for s in sents if s.end <= start][-n:]
    after = [s.text for s in sents if s.start >= end][:n]
    return " ".join(before), " ".join(after)


def task_record(db: Session, t: Task, users: dict[str, User]) -> Record:
    doc = db.get(Document, t.document_id) if t.document_id else None
    before, after = doc_context(doc, t.source_start, t.source_end)
    by = users.get(t.assigned_by or t.decided_by or "")
    lines = [
        f"Görev {t.key or '#' + str(t.id)}: {t.source_quote or t.title}",
        f"Atayan: {by.name if by else '—'} · Teslim: {t.due_date.isoformat() if t.due_date else 'belirtilmemiş'}"
        f" · Tahmini süre: {t.est_days:g} gün · Durum: {t.status}",
    ]
    if before or after:
        lines.append(f"Dokümanda öncesi: {before or '—'} | sonrası: {after or '—'}")
    if t.reasons:
        lines.append("Bu kişiye verilme gerekçeleri: " + "; ".join(t.reasons))
    label = f"{t.key or '#' + str(t.id)}" + (f" · {doc.title} {t.source_ref}" if doc else "")
    return Record("\n".join(lines), label)


def retrieve(db: Session, me: User, question: str, tasks: list[Task], users: dict[str, User]) -> list[Record]:
    """Görev kayıtları + soruya en benzeyen doküman cümleleri (encoder ile)."""
    k = get_settings().rag_top_k
    task_recs = [task_record(db, t, users) for t in tasks]

    docs: dict[int, Document] = {}
    for t in tasks:
        if t.document_id and t.document_id not in docs:
            d = db.get(Document, t.document_id)
            if d:
                docs[d.id] = d
    for d in db.scalars(select(Document).order_by(Document.created_at.desc()).limit(50)):
        if me.id in (d.shared_with or []):
            docs.setdefault(d.id, d)

    sent_recs: list[Record] = []
    for d in docs.values():
        for s in split_sentences(d.text):
            sent_recs.append(Record(s.text, f"{d.title} {s.ref}"))

    emb = _embedder()
    pool = task_recs + sent_recs
    if not pool:
        return []
    qv = emb.encode([question])[0]
    vecs = emb.encode([r.text for r in pool])
    sims = vecs @ qv
    # Görev kayıtları kısa listede öncelikli (kullanıcının kendi işi); kalan yerleri cümleler doldurur.
    t_order = sorted(range(len(task_recs)), key=lambda i: -sims[i])[: max(1, k // 2)]
    s_idx = np.argsort(-sims[len(task_recs):])[: k - len(t_order)] + len(task_recs) if sent_recs else []
    chosen = [pool[i] for i in t_order] + [pool[int(i)] for i in s_idx]
    seen, out = set(), []
    for r in chosen:
        if r.text not in seen:
            seen.add(r.text)
            out.append(r)
    return out


# Sabit talimatlar başta, değişen kayıtlar sonda: aynı önek tekrar işlenmez (önek önbelleği).
SYSTEM = """Sen {org} kurumunun iç görev asistanısın.
Kurallar: Yalnızca KAYITLAR'daki bilgiyi kullan; yoksa "Bu bilgi kayıtlarda yok." de. Uydurma.
Her bilginin sonuna kaynağını [K1] biçiminde yaz. Türkçe, kısa yaz; gerekirse en fazla 4 madde.
Bugün: {today}

KAYITLAR:
{records}"""

MAX_RECORD_CHARS = 420  # her kayıt en fazla bu kadar karakter: istem kısa = prefill hızlı


def _clip(text: str, n: int = MAX_RECORD_CHARS) -> str:
    return text if len(text) <= n else text[: n - 1].rsplit(" ", 1)[0] + "…"


def build_system(records: list[Record], org: str) -> str:
    body = "\n".join(f"[K{i + 1}] {_clip(r.text)}" for i, r in enumerate(records)) or "(kayıt yok)"
    return SYSTEM.format(org=org, today=date.today().isoformat(), records=body)


def prepare(question: str, records: list[Record], history: list[Message]) -> tuple[str, list[ChatTurn]]:
    turns = [ChatTurn(m.role, _clip(m.text, 300)) for m in history[-2:] if m.text]
    turns.append(ChatTurn("user", question))
    return build_system(records, get_settings().org_name), turns


def finalize(decoder: OllamaDecoder, g: Generation, records: list[Record]) -> tuple[str, list[str]]:
    """Kaynak numaralarını etikete çevirir; süre ve olasılık bilgisini ekler."""
    cited = sorted({int(n) for n in CITE.findall(g.text) if 0 < int(n) <= len(records)})
    text = CITE.sub(lambda m: f"[{m.group(1)}]", g.text)
    if records and not cited:
        text += "\n\n_Bu cevap kaynak göstermedi; kayıtlarla karşılaştırarak değerlendirin._"
    meta = f"Model: {decoder.model} · {g.timing()}"
    if g.mean_token_prob is not None:
        meta += f" · ort. token olasılığı %{round(g.mean_token_prob * 100)}"
    return text, [f"[{n}] {records[n - 1].label}" for n in cited] + [meta]


def generate(
    decoder: OllamaDecoder, question: str, records: list[Record], history: list[Message]
) -> tuple[str, list[str]]:
    """Akışsız üretim (testler ve akış desteklemeyen istemciler için)."""
    system, turns = prepare(question, records, history)
    try:
        g = decoder.generate(system, turns)
    except DecoderUnavailable as e:
        return f"Dil modeline şu an ulaşılamıyor ({e}).", []
    return finalize(decoder, g, records)
