"""Kural tabanlı sahte sağlayıcı.

Gerçek model bağlanana kadar uygulamanın uçtan uca çalışmasını sağlar. Türkçe
toplantı notlarında "-meli/-malı", "gerekiyor", "şart" gibi yükümlülük ifadeleri ve
hata bildirimleri geçen cümleleri görev olarak alır. Kalitesi bilinçli olarak
basittir; asıl çıkarım LLM katmanı kurulduğunda yapılacak.
"""
import re

from .base import ChatTurn, ExtractedTask

OBLIGATION = re.compile(
    r"(meli\b|malı\b|melidir|malıdır|gerekiyor|gerekir|gerekmektedir|şart\b|yapılacak|eklenmeli|"
    r"düşüyor|hata\b|hatası|çalışmıyor)",
    re.IGNORECASE,
)
SECTION = re.compile(r"§\s*(\d+)")

TAG_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("backend", ("api", "servis", "uç nokta", "endpoint", "veritabanı", "backend", "limit")),
    ("mobile", ("ios", "android", "mobil", "face id", "uygulama içi")),
    ("ios", ("ios", "face id", "swift")),
    ("qa", ("test", "regresyon", "doğrula")),
    ("security", ("kvkk", "maskel", "güvenlik", "tckn", "iban", "denetim", "log")),
    ("devops", ("staging", "ölçekleme", "deploy", "ortam", "sunucu", "kubernetes", "ci/cd")),
    ("frontend", ("arayüz", "ekran", "web", "frontend", "react")),
]

EST_RULES: list[tuple[tuple[str, ...], float]] = [
    (("yeniden yaz", "taşın", "mimari"), 5.0),
    (("test", "regresyon", "maskel"), 3.0),
]


def _tags_for(text: str) -> list[str]:
    low = text.lower()
    tags = [tag for tag, keys in TAG_RULES if any(k in low for k in keys)]
    return tags or ["general"]


def _estimate(text: str) -> float:
    low = text.lower()
    for keys, days in EST_RULES:
        if any(k in low for k in keys):
            return days
    return 2.0


def _title_from(sentence: str) -> str:
    s = sentence.strip().rstrip(".;:")
    s = re.sub(r"^(bu nedenle|ayrıca|ancak|ve|bu sprintte)\s+", "", s, flags=re.IGNORECASE)
    s = s[0].upper() + s[1:] if s else s
    return s if len(s) <= 110 else s[:107].rstrip() + "…"


class MockProvider:
    name = "mock"

    def extract_tasks(self, document_text: str, doc_type: str) -> list[ExtractedTask]:
        tasks: list[ExtractedTask] = []
        offset = 0
        paragraphs = document_text.split("\n")
        para_no = 0
        for para in paragraphs:
            start_of_para = offset
            offset += len(para) + 1
            if not para.strip():
                continue
            para_no += 1
            m = SECTION.search(para)
            ref = f"§{m.group(1)}" if m else f"¶{para_no}"
            # cümlelere böl, kaynak konumlarını koru
            for sm in re.finditer(r"[^.!?]+[.!?]?", para):
                sentence = sm.group(0).strip()
                if len(sentence) < 15 or not OBLIGATION.search(sentence):
                    continue
                # bölüm başlığını ("§2 Limit kontrolü.") alıntıdan çıkar
                clean = SECTION.sub("", sentence).strip()
                rel = para.find(clean)
                abs_start = start_of_para + (rel if rel >= 0 else sm.start())
                tasks.append(
                    ExtractedTask(
                        title=_title_from(clean),
                        detail="",
                        tags=_tags_for(clean),
                        est_days=_estimate(clean),
                        source_ref=ref,
                        source_quote=clean,
                        source_start=abs_start,
                        source_end=abs_start + len(clean),
                    )
                )
        return tasks

    def chat(self, turns: list[ChatTurn], context: str) -> str:
        return (
            "Bu soruyu yanıtlayacak dil modeli henüz bağlanmadı. Şu an görevlerinizi, "
            "sizinle paylaşılan dokümanları ve bu haftaki teslimleri sorabilirsiniz."
        )
