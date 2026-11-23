"""KVKK için basit anonimleştirme: dokümanı veri setine koymadan önce kişisel verileri maskeler.

Kapsam: e-posta, telefon, TCKN (11 hane), IBAN, kullanıcının verdiği kişi adları.
Kural tabanlıdır; kaydetmeden önce sonucu gözle kontrol etmek gerekir.
"""
import re

PATTERNS: list[tuple[str, str]] = [
    (r"[\w.+-]+@[\w-]+\.[\w.-]+", "[E-POSTA]"),
    (r"\bTR\s?\d{2}(?:\s?\d{4}){5}\s?\d{2}\b", "[IBAN]"),
    (r"(?<!\d)[1-9]\d{10}(?!\d)", "[TCKN]"),
    (r"(?:\+90[\s-]?)?\(?0?5\d{2}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}", "[TELEFON]"),
]


def anonymize(text: str, names: list[str] | None = None) -> tuple[str, dict[str, int]]:
    """Maskelenmiş metin ve hangi türden kaç değişiklik yapıldığı."""
    counts: dict[str, int] = {}
    for rx, tag in PATTERNS:
        text, n = re.subn(rx, tag, text)
        if n:
            counts[tag] = counts.get(tag, 0) + n
    # Kişi adları: "Ahmet Yılmaz" -> "Kişi-1"; ekleri korunur ("Ahmet'e" -> "Kişi-1'e")
    for i, name in enumerate(n.strip() for n in (names or []) if n.strip()):
        rx = rf"(?<![\wçğıöşüÇĞİÖŞÜ]){re.escape(name)}(?![\wçğıöşüÇĞİÖŞÜ])"
        text, k = re.subn(rx, f"Kişi-{i + 1}", text)
        if k:
            counts["[İSİM]"] = counts.get("[İSİM]", 0) + k
    return text, counts
