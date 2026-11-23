"""Sağlayıcıların ortak metin yardımcıları."""
import re
from dataclasses import dataclass

SECTION = re.compile(r"§\s*(\d+)")
OBLIGATION = re.compile(
    r"(meli\b|malı\b|melidir|malıdır|gerekiyor|gerekir|gerekmektedir|şart\b|yapılacak|eklenmeli|"
    r"düşüyor|hata\b|hatası|çalışmıyor|çöküyor)",
    re.IGNORECASE,
)

EST_RULES: list[tuple[tuple[str, ...], float]] = [
    (("yeniden yaz", "taşın", "mimari"), 5.0),
    (("test", "regresyon", "maskel"), 3.0),
]


@dataclass
class Sentence:
    text: str  # bölüm etiketi ("§2 Başlık.") ayıklanmış cümle
    ref: str  # "§2" ya da "¶3"
    start: int  # dokümandaki karakter konumu
    end: int


def _is_title_line(line: str) -> bool:
    t = line.strip()
    return not SECTION.search(t) and not re.search(r"[.!?:;]$", t) and len(t.split()) <= 12


def split_sentences(document_text: str, min_len: int = 15) -> list[Sentence]:
    """Dokümanı paragraflara ve cümlelere böler; her cümlenin dokümandaki yerini korur.

    - "v3.2" gibi sayı içindeki noktalar cümle sonu sayılmaz.
    - "§2 Limit kontrolü." gibi bölüm başlıkları cümle sayılmaz.
    - Noktalama ile bitmeyen kısa satırlar (doküman başlığı vb.) cümle sayılmaz.
    - Noktalı virgül cümleyi bölmez: "uygulama çöküyor; hata kaydı ektedir" tek cümledir.
    """
    out: list[Sentence] = []
    offset = 0
    para_no = 0
    for para in document_text.split("\n"):
        start_of_para = offset
        offset += len(para) + 1
        if not para.strip():
            continue
        para_no += 1
        m = SECTION.search(para)
        ref = f"§{m.group(1)}" if m else f"¶{para_no}"
        if _is_title_line(para):
            continue
        pos = 0
        for raw in re.split(r"(?<=[.!?])\s+", para):
            idx = para.find(raw, pos)
            pos = idx + len(raw) if idx >= 0 else pos
            raw = raw.strip()
            is_heading = raw.startswith("§") and len(SECTION.sub("", raw).split()) <= 3
            clean = SECTION.sub("", raw).strip()
            if is_heading or len(clean) < min_len:
                continue
            rel = para.find(clean, max(idx, 0))
            abs_start = start_of_para + (rel if rel >= 0 else max(idx, 0))
            out.append(Sentence(clean, ref, abs_start, abs_start + len(clean)))
    return out


def estimate_days(text: str) -> float:
    low = text.lower()
    for keys, days in EST_RULES:
        if any(k in low for k in keys):
            return days
    return 2.0


def title_from(sentence: str) -> str:
    s = sentence.strip().rstrip(".;:")
    s = re.sub(r"^(bu nedenle|ayrıca|ancak|ve|bu sprintte)\s+", "", s, flags=re.IGNORECASE)
    s = s[0].upper() + s[1:] if s else s
    return s if len(s) <= 110 else s[:107].rstrip() + "…"
