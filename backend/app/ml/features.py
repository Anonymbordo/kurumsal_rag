"""Türkçe kip (söz eylemi) özellikleri.

Embedding'ler cümlenin konusunu güçlü, kipini zayıf kodlar: "sayfalama eklendi" ile
"sayfalama eklenmeli" neredeyse aynı vektöre düşer. Bu özellikler kip bilgisini açıkça
verir; lineer probe her birine ne kadar güveneceğini veriden öğrenir.

Her özellik 0/1'dir (bazıları sayım), açıklanabilir ve dil bilgisine dayanır.
"""
import re

import numpy as np

# Türkçe yüklem sondadır: zaman/kip ekleri cümlenin SON kelimesinde aranır
# (ortadaki "testi", "kodu" gibi isim halleri geçmiş zaman sanılmasın diye).
# (ad, açıklama, düzenli ifade, nerede: "son" = son kelime, "tum" = tüm cümle)
PATTERNS: list[tuple[str, str, str | None, str]] = [
    ("yukumluluk", "-meli/-malı, gerekiyor, şart, lazım", r"m[ae]l[ıi](d[ıi]r)?$|^gerek(iyor|ir|mektedir|li)?$|^şart(tır)?$|^lazım$", "son"),
    # -acak/-ecek; konuşma dilinde 1. şahıs üstlenme de bu sütunda: -acağım/-eceğiz, "düzeltirim", "bakarım"
    ("gelecek", "-acak/-ecek, -acağım, -ırım (üstlenme)", r"(y)?[ae]c[ae]k(t[ıi]r|s[ıi]n[ıi]z)?$|(y)?[ae]c[ae]ğ[ıi](m|z)$|..(ır|ir|ur|ür|ar|er)[ıiuü]m$", "son"),
    ("emir_istek", "-sın/-sin, -alım/-elim", r"..s[ıiuü]n(lar|ler)?$|(y)?[ae]l[ıi]m$", "son"),
    ("gecmis", "-dı/-tı/-mış (tamamlanmış)", r"..[dt][ıiuü](k|lar|ler)?$|m[ıiuü]ş(t[ıi]r|lar)?$", "son"),
    ("suren", "-ıyor (süren durum)", r"yor(uz|lar|um|sun|du)?$", "son"),
    ("soru_rica", "mi? / rica / -abilir mi / sevinirim", r"\bm[ıiuü](s[ıiuü]n|y[ıi]z)?\s*\?|\brica\b|sevinirim|olur mu|[ae]bilir\s+m[ıiuü]", "tum"),
    ("ok_isareti", "→ / -> (sorumlu gösterimi)", r"→|->", "tum"),
    ("hitap", "Cümle başında 'İsim,' (doğrudan hitap)", None, "tum"),
    ("ihtiyac_yok", "gerek yok / gerekmez", r"gerek\s+yok|gerekmez|ihtiyaç\s+yok", "tum"),
    ("bilgi_onek", "Not:, Bilgi:, Genel hatırlatma", r"^\s*(not|bilgi|hatırlatma|genel hatırlatma|duyuru)\s*:", "tum"),
    ("bitti_kelime", "tamamlandı, düzeltildi, yayına alındı…", r"tamamland|düzeltild|giderild|yayın[ae] al[ıi]n|canlıya (sorunsuz )?çıktı|onayland|bitirild|çözüld", "tum"),
    ("kapsam", "kapsam dışı / kapsamına almıyoruz", r"kapsam", "tum"),
    ("toplanti", "toplantı / kurul bilgisi", r"toplantı|kurul\b", "tum"),
    ("olumsuz", "olumsuz yüklem (-madı, -mıyor, değil)", r"m[ae](d[ıi]|y[ıi]|z|m[ıi]ş)$|m[ıiuü]yor$|^değil", "son"),
    ("isim_cumlesi", "yüklemsiz/isim cümlesi (ör. '… → Mert', '… var')", r"^(var|yok)$|^[A-ZÇĞİÖŞÜ]", "son_ham"),
]

FEATURE_NAMES = [p[0] for p in PATTERNS]
_COMPILED = [(n, re.compile(r, re.IGNORECASE if w != "son_ham" else 0) if r else None, w) for n, _, r, w in PATTERNS]
_VOCATIVE = re.compile(r"^\s*[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(\s*&\s*[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)?\s*,")
_WORD = re.compile(r"[\wçğıöşüÇĞİÖŞÜ']+")


def _lower(t: str) -> str:
    return t.replace("I", "ı").replace("İ", "i").lower()


def features(sentence: str) -> np.ndarray:
    low = _lower(sentence)
    words = _WORD.findall(sentence)
    last_raw = words[-1].split("'")[0] if words else ""
    last = _lower(last_raw)
    out = []
    for name, rx, where in _COMPILED:
        if name == "hitap":
            hit = bool(_VOCATIVE.search(sentence))
        elif where == "son":
            hit = bool(last) and bool(rx.search(last))
        elif where == "son_ham":
            hit = bool(last_raw) and bool(rx.search(last_raw))
        else:
            hit = bool(rx.search(low))
        out.append(1.0 if hit else 0.0)
    return np.array(out, dtype=np.float32)


def feature_matrix(sentences: list[str]) -> np.ndarray:
    if not sentences:
        return np.zeros((0, len(FEATURE_NAMES)), dtype=np.float32)
    return np.stack([features(s) for s in sentences])


def clauses(sentence: str) -> list[str]:
    """Yan cümleler: virgül/noktalı virgül/' ama ' ile ayrılmış, yeterince uzun parçalar."""
    parts = [p.strip() for p in re.split(r"[;,]\s+|\s+ama\s+|\s+fakat\s+", sentence)]
    return [p for p in parts if len(p.split()) >= 3]
