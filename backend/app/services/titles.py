"""Görev kartları için kısa başlık.

Görev cümlesinin kendisi kaynak olarak korunur (source_quote); kartta gösterilen başlık
3-7 kelimelik bir özettir. Decoder bağlıysa başlık ondan istenir ve kaynakla karşılaştırılır
(cümlede geçmeyen kavram içeriyorsa reddedilir). Decoder yoksa kurala dayalı kısaltma kullanılır.
Üretim arka planda yapılır: lider görev listesini beklemeden görür, başlıklar birkaç saniye içinde güncellenir.
"""
import re
import threading

from sqlalchemy import select

from ..db import SessionLocal
from ..llm import ChatTurn
from ..llm.decoder import DecoderUnavailable, get_decoder
from ..models import Task

VOCATIVE = re.compile(r"^\s*[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)?\s*[,:]\s+")
MAX_WORDS = 9

PROMPT = """Bir iş cümlesinden kısa bir görev başlığı yaz.
Kurallar: 3-7 kelime. İsim tamlaması kullan, emir ya da "-meli" kullanma. Kişi adı ve tarih yazma.
Cümlede olmayan hiçbir kavram ekleme. Sadece başlığı yaz, tırnak ve nokta koyma.

Cümle: Pelin, iOS tarafında biyometrik giriş ekranındaki klavye üst üste binme hatasını bu hafta içinde düzeltmeli.
Başlık: iOS biyometrik girişte klavye çakışma hatası

Cümle: Staging veritabanı çok şişti, test verilerini temizleyip anonimleştirilmiş güncel bir dump almak lazım.
Başlık: Staging veritabanı temizliği ve anonim dump

Cümle: Toplu fatura dışa aktarma uç noktasının asenkron kuyruk yapısına geçirilmesi gerekiyor.
Başlık: Fatura dışa aktarmanın asenkron kuyruğa taşınması

Cümle: {sentence}
Başlık:"""


def rule_title(sentence: str, limit: int = 70) -> str:
    """Hitabı ("Emre, ...") at, kelime sınırında kısalt."""
    s = VOCATIVE.sub("", sentence.strip()).rstrip(".;: ")
    if s and s[0].islower() and not any(ch.isupper() for ch in s.split()[0][1:]):
        s = s[0].upper() + s[1:]
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "…"


_W = re.compile(r"[a-zçğıöşü0-9]{3,}")


def _stems(t: str) -> set[str]:
    return {w[:5] for w in _W.findall(t.replace("I", "ı").replace("İ", "i").lower())}


def acceptable(title: str, sentence: str) -> bool:
    """Üretilen başlık kısa mı ve kelimeleri cümlede geçiyor mu?"""
    words = title.split()
    if not (2 <= len(words) <= MAX_WORDS) or len(title) > 80 or "\n" in title:
        return False
    st = _stems(title)
    return bool(st) and len(st & _stems(sentence)) / len(st) >= 0.6


def llm_title(sentence: str) -> str | None:
    dec = get_decoder()
    if dec is None:
        return None
    try:
        g = dec.generate("Kısa ve doğru görev başlıkları yazarsın.", [ChatTurn("user", PROMPT.format(sentence=sentence))],
                         max_tokens=24, temperature=0.0)
    except DecoderUnavailable:
        return None
    t = g.text.strip().splitlines()[0] if g.text.strip() else ""
    t = re.sub(r"^(başlık\s*:\s*)", "", t, flags=re.IGNORECASE).strip(" \"'.“”")
    return t if acceptable(t, sentence) else None


def fill_short_titles(task_ids: list[int] | None = None, limit: int = 300) -> int:
    """Kısa başlığı olmayan görevlere başlık yazar. Decoder yoksa hiçbir şey yapmaz (kural başlığı kullanılır)."""
    if get_decoder() is None:
        return 0
    done = 0
    with SessionLocal() as db:
        q = select(Task).where(Task.short_title.is_(None))
        if task_ids:
            q = q.where(Task.id.in_(task_ids))
        for t in db.scalars(q.order_by(Task.id.desc()).limit(limit)).all():
            title = llm_title(t.source_quote or t.title)
            t.short_title = title or rule_title(t.source_quote or t.title)
            db.commit()
            done += 1
    return done


def fill_in_background(task_ids: list[int] | None = None, limit: int = 300) -> None:
    threading.Thread(target=fill_short_titles, args=(task_ids, limit), daemon=True).start()


def display_title(t: Task) -> str:
    return t.short_title or rule_title(t.source_quote or t.title)
