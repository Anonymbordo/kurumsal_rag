"""Sağlayıcıların ortak metin yardımcıları."""
import re
from dataclasses import dataclass

SECTION = re.compile(r"§\s*(\d+)")
OBLIGATION = re.compile(
    r"(meli\b|malı\b|melidir|malıdır|gerekiyor|gerekir|gerekmektedir|şart\b|yapılacak|eklenmeli|"
    r"düşüyor|hata\b|hatası|çalışmıyor|çöküyor)",
    re.IGNORECASE,
)

# Konuşma dilinde iş üstlenme (toplantı dökümleri): "ben bakarım", "yarın düzeltirim", "hallederim".
# Türkçe'de yüklem yan cümlenin sonundadır: yalnızca her yan cümlenin SON kelimesine bakılır.
# Aksi halde "oturum", "sürüm", "bildirim" gibi isimler 1. şahıs fiil sanılır.
_SELF_VERB = re.compile(r"\w{2,}(?:acağım|eceğim|ırım|irim|urum|ürüm|arım|erim|ayım|eyim|ıyorum|iyorum|uyorum|üyorum)$")
_SELF_PHRASE = re.compile(r"(?:^|\s)(bana kalsın|bende kalsın|ben hallederim|ben bakarım)(?=$|[\s,.;:!?])")
_CLAUSE = re.compile(r"[,.;:!?]|\s(?:ve|ama|fakat|ancak|çünkü)\s")


# Toplantı dökümü satırı "Ayşe Kaya: ..." diye başlar (konuşmacı etiketi).
_SPEAKER_LINE = re.compile(r"^\s*([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:[ \t]+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+){0,2}):\s+")
_NOT_SPEAKER = {"not", "nota", "hatırlatma", "genel hatırlatma", "duyuru", "bilgi", "bilgilendirme", "önemli",
                "katılımcılar", "katılanlar", "gündem", "karar", "kararlar", "tarih", "konu", "kime", "ekip", "blocker"}


def spoken_by(document_text: str, pos: int) -> str | None:
    """`pos` konumundaki cümle bir konuşmacı satırındaysa konuşanın adı."""
    if pos is None or pos < 0:
        return None
    line_start = document_text.rfind("\n", 0, pos) + 1
    m = _SPEAKER_LINE.match(document_text[line_start: line_start + 80])
    if not m or m.group(1).replace("I", "ı").replace("İ", "i").lower() in _NOT_SPEAKER:
        return None
    return m.group(1)


def strip_speaker_label(text: str) -> str:
    m = _SPEAKER_LINE.match(text)
    if m and m.group(1).replace("I", "ı").replace("İ", "i").lower() not in _NOT_SPEAKER:
        return text[m.end():]
    return text


def spoken_commitment(document_text: str, sentence: str, pos: int) -> bool:
    """Toplantı dökümünde konuşan kişi işi kendisi üstleniyor mu? ("bunu ben düzeltirim")"""
    return spoken_by(document_text, pos) is not None and self_commitment(strip_speaker_label(sentence))


def self_commitment(text: str) -> bool:
    low = text.replace("I", "ı").replace("İ", "i").lower()
    if _SELF_PHRASE.search(low):
        return True
    for clause in _CLAUSE.split(low):
        words = re.findall(r"[a-zçğıöşü]+", clause)
        if words and _SELF_VERB.search(words[-1]):
            return True
    return False

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


BULLET = re.compile(r"^\s*(?:[-–•*]|\d+[.)])\s+")


def _is_title_line(line: str, first: bool) -> bool:
    """Doküman başlığı (ilk satır, noktalamasız ve kısa) ya da liste başlığı ("Gündem:")."""
    t = line.strip()
    if SECTION.search(t) or BULLET.match(t):
        return False
    words = t.split()
    if first and not re.search(r"[.!?]$", t) and len(words) <= 12:
        return True
    if t.endswith(":") and len(words) <= 8:
        return True
    # Ara başlık: "Teknik Borçlar, Altyapı ve Açık Sorular" — kısa, noktalamasız, çoğu kelime büyük harfle
    content = [w for w in words if len(w) > 2]
    caps = sum(1 for w in content if w[0].isupper())
    return (
        not re.search(r"[.!?]$", t)
        and len(words) <= 8
        and bool(content)
        and caps / len(content) >= 0.6
        and not OBLIGATION.search(t)
    )


def split_sentences(document_text: str, min_len: int = 15) -> list[Sentence]:
    """Dokümanı paragraflara ve cümlelere böler; her cümlenin dokümandaki yerini korur.

    - "v3.2" gibi sayı içindeki noktalar cümle sonu sayılmaz.
    - "§2 Limit kontrolü." gibi bölüm başlıkları cümle sayılmaz.
    - Doküman başlığı (ilk kısa satır) ve "Gündem:" gibi liste başlıkları cümle sayılmaz.
    - Madde işaretleri ("- ", "• ", "1) ") cümleden ayıklanır.
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
        if _is_title_line(para, first=para_no == 1):
            continue
        pos = 0
        for raw in re.split(r"(?<=[.!?])\s+", para):
            idx = para.find(raw, pos)
            pos = idx + len(raw) if idx >= 0 else pos
            raw = BULLET.sub("", raw.strip())
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
    first = s.split()[0] if s else ""
    if s and not any(ch.isupper() for ch in first[1:]):  # "iOS", "eKYC" gibi kelimeleri bozma
        s = s[0].upper() + s[1:]
    return s if len(s) <= 110 else s[:107].rstrip() + "…"
