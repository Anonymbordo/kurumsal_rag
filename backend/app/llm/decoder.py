"""Yerel decoder (üretken model) istemcisi.

Mimari:
  encoder (e5)  -> anlar, sınıflandırır, ilgili kayıtları bulur (retrieval)
  decoder (LLM) -> yalnızca o kayıtlara bakarak Türkçe cevap yazar (generation)

Decoder ile encoder arasında çapraz dikkat (cross-attention) yok: encoder'ın bulduğu
kayıtlar metin olarak decoder'ın istemine (prompt) konur. Decoder bu bağlamın üzerinde
nedensel maskeli (causal) öz-dikkatle, her adımda yalnızca önceki token'lara bakarak
bir sonraki token'ı üretir: son gizli durum -> LM head -> logit -> softmax -> olasılık.

Model sunucusu: Ollama (llama.cpp tabanlı, CPU'da 4-bit GGUF). Kurum içinde çalışır,
veri dışarı çıkmaz. Sunucu kapalıysa uygulama decoder'sız (şablon cevaplarla) çalışmaya devam eder.
"""
import json
import math
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from functools import lru_cache

from ..config import get_settings
from .base import ChatTurn


@dataclass
class Generation:
    text: str
    # Üretilen token'ların ortalama olasılığı (softmax çıktısı): exp(ortalama log-olasılık).
    # Sunucu log-olasılık döndürmüyorsa None.
    mean_token_prob: float | None = None
    min_token_prob: float | None = None
    seconds: float = 0.0
    tokens: int = 0
    raw: dict = field(default_factory=dict, repr=False)


class DecoderUnavailable(RuntimeError):
    pass


class OllamaDecoder:
    def __init__(self, url: str, model: str, timeout: float = 120.0, logprobs: bool = True):
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.logprobs = logprobs
        self._ok_until = 0.0

    def _post(self, path: str, body: dict, timeout: float) -> dict:
        req = urllib.request.Request(
            self.url + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="ignore")[:300]
            raise DecoderUnavailable(f"Decoder hatası ({e.code}): {detail}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise DecoderUnavailable(f"Decoder sunucusuna ulaşılamadı: {e}") from e

    def available(self) -> bool:
        """Sunucu açık ve model indirilmiş mi? Sonuç 30 sn önbelleklenir."""
        now = time.time()
        if now < self._ok_until:
            return True
        try:
            req = urllib.request.Request(self.url + "/api/tags")
            with urllib.request.urlopen(req, timeout=2) as r:
                names = {m.get("name", "") for m in json.loads(r.read().decode()).get("models", [])}
        except Exception:
            return False
        ok = self.model in names or f"{self.model}:latest" in names
        if ok:
            self._ok_until = now + 30
        return ok

    def generate(self, system: str, turns: list[ChatTurn], max_tokens: int = 400, temperature: float = 0.2) -> Generation:
        body = {
            "model": self.model,
            "stream": False,
            "messages": [{"role": "system", "content": system}] + [{"role": t.role, "content": t.content} for t in turns],
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if self.logprobs:
            body["logprobs"] = True  # destekleyen sürümlerde token başına log-olasılık döner
        t0 = time.time()
        data = self._post("/api/chat", body, self.timeout)
        text = (data.get("message") or {}).get("content", "").strip()
        lps = [x["logprob"] for x in (data.get("logprobs") or []) if isinstance(x, dict) and "logprob" in x]
        mean_p = math.exp(sum(lps) / len(lps)) if lps else None
        min_p = math.exp(min(lps)) if lps else None
        return Generation(
            text=text, mean_token_prob=mean_p, min_token_prob=min_p, seconds=time.time() - t0,
            tokens=int(data.get("eval_count") or len(lps)), raw=data,
        )


@lru_cache
def _client() -> OllamaDecoder | None:
    s = get_settings()
    if s.decoder != "ollama":
        return None
    return OllamaDecoder(s.decoder_url, s.decoder_model, s.decoder_timeout, s.decoder_logprobs)


def get_decoder() -> OllamaDecoder | None:
    """Kullanılabilir decoder'ı döndürür; kapalı/yapılandırılmamışsa None."""
    c = _client()
    return c if c is not None and c.available() else None
