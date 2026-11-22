from ..config import get_settings
from .base import ChatTurn, ExtractedTask, LLMProvider
from .mock import MockProvider

__all__ = ["ChatTurn", "ExtractedTask", "LLMProvider", "get_provider"]


def get_provider() -> LLMProvider:
    """Ayarlardaki GA_LLM_PROVIDER değerine göre sağlayıcıyı döndürür.

    Yeni bir sağlayıcı (ör. yerel model sunucusu) eklemek için:
      1. app/llm/ altında LLMProvider arayüzünü uygulayan bir sınıf yazın.
      2. Aşağıya bir dal ekleyin.
    """
    name = get_settings().llm_provider
    if name == "mock":
        return MockProvider()
    raise ValueError(
        f"Bilinmeyen LLM sağlayıcısı: {name!r}. LLM mimarisi netleşene kadar 'mock' kullanın."
    )
