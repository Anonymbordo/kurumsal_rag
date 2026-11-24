"""Kural tabanlı sahte sağlayıcı.

Model gerektirmeden uygulamanın uçtan uca çalışmasını sağlar. Türkçe toplantı
notlarında "-meli/-malı", "gerekiyor", "şart" gibi yükümlülük ifadeleri ve hata
bildirimleri geçen cümleleri görev olarak alır. Karşılaştırma tabanı (baseline)
olarak da kullanılır.
"""
from .base import ChatTurn, ExtractedTask
from .text import OBLIGATION, estimate_days, self_commitment, split_sentences, title_from

TAG_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("backend", ("api", "servis", "uç nokta", "endpoint", "veritabanı", "backend", "limit")),
    ("mobile", ("ios", "android", "mobil", "face id", "uygulama içi")),
    ("ios", ("ios", "face id", "swift")),
    ("qa", ("test", "regresyon", "doğrula")),
    ("security", ("kvkk", "maskel", "güvenlik", "tckn", "iban", "denetim", "log")),
    ("devops", ("staging", "ölçekleme", "deploy", "ortam", "sunucu", "kubernetes", "ci/cd")),
    ("frontend", ("arayüz", "ekran", "web", "frontend", "react")),
]


def _tags_for(text: str) -> list[str]:
    low = text.lower()
    tags = [tag for tag, keys in TAG_RULES if any(k in low for k in keys)]
    return tags or ["general"]


class MockProvider:
    name = "mock"

    def extract_tasks(self, document_text: str, doc_type: str) -> list[ExtractedTask]:
        tasks: list[ExtractedTask] = []
        for s in split_sentences(document_text):
            if not OBLIGATION.search(s.text) and not (doc_type == "meeting" and self_commitment(s.text)):
                continue
            tasks.append(
                ExtractedTask(
                    title=title_from(s.text),
                    tags=_tags_for(s.text),
                    est_days=estimate_days(s.text),
                    source_ref=s.ref,
                    source_quote=s.text,
                    source_start=s.start,
                    source_end=s.end,
                )
            )
        return tasks

    def chat(self, turns: list[ChatTurn], context: str) -> str:
        return (
            "Bu soruyu yanıtlayacak dil modeli henüz bağlanmadı. Şu an görevlerinizi, "
            "sizinle paylaşılan dokümanları ve bu haftaki teslimleri sorabilirsiniz."
        )
