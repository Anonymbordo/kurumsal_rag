"""LLM sağlayıcı arayüzü.

Uygulamanın geri kalanı modele yalnızca bu arayüz üzerinden erişir. Böylece
model mimarisi (hangi model, nasıl sunulacağı, RAG yapısı) netleştiğinde sadece
yeni bir sağlayıcı sınıfı yazılır; API ve arayüz değişmez.
"""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ExtractedTask:
    """Dokümandan çıkarılan tek bir görev. Kişi ataması burada YOK:
    öneri mantığı ayrı bir modülde (services/assignment.py) çalışır."""

    title: str
    detail: str = ""
    tags: list[str] = field(default_factory=list)  # örn. ["backend", "api"]
    est_days: float = 1.0
    source_ref: str = ""  # örn. "§2"
    source_quote: str = ""  # dokümandan birebir alıntı
    source_start: int = -1  # alıntının dokümandaki karakter konumu
    source_end: int = -1
    detect_score: float | None = None  # modelin "bu bir görev" olasılığı (0–1); kural tabanlıda yok


@dataclass
class ChatTurn:
    role: str  # "user" | "assistant" | "system"
    content: str


class LLMProvider(Protocol):
    name: str

    def extract_tasks(self, document_text: str, doc_type: str) -> list[ExtractedTask]:
        """Doküman metninden görevleri çıkarır. Her görev kaynağına bağlı olmalı."""
        ...

    def chat(self, turns: list[ChatTurn], context: str) -> str:
        """Serbest sohbet. `context` kullanıcının görevleri, paylaşılan dokümanlar gibi
        uygulamanın verdiği bağlamdır."""
        ...
