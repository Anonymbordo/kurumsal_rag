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

CPU'da süre nereye gider?
  load    : model ağırlıklarının belleğe yüklenmesi (keep_alive ile bir kez)
  prefill : istemdeki tüm token'ların işlenmesi (istem uzadıkça artar; en pahalı kısım)
  decode  : cevabın token token üretilmesi (akışla kullanıcıya hemen gösterilir)
"""
import json
import math
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
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
    prompt_tokens: int = 0
    load_s: float = 0.0
    prefill_s: float = 0.0
    decode_s: float = 0.0
    raw: dict = field(default_factory=dict, repr=False)

    def timing(self) -> str:
        parts = [f"{self.seconds:.1f} sn"]
        if self.prompt_tokens:
            parts.append(f"istem {self.prompt_tokens} token / {self.prefill_s:.1f} sn")
        if self.tokens and self.decode_s:
            parts.append(f"üretim {self.tokens} token / {self.decode_s:.1f} sn ({self.tokens / self.decode_s:.0f} token/sn)")
        if self.load_s > 1:
            parts.append(f"yükleme {self.load_s:.1f} sn")
        return " · ".join(parts)


class DecoderUnavailable(RuntimeError):
    pass


def _ns(d: dict, key: str) -> float:
    return float(d.get(key) or 0) / 1e9


class OllamaDecoder:
    def __init__(
        self,
        url: str,
        model: str,
        timeout: float = 120.0,
        logprobs: bool = True,
        keep_alive: str = "30m",
        num_ctx: int = 2048,
        max_tokens: int = 256,
    ):
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.logprobs = logprobs
        self.keep_alive = keep_alive
        self.num_ctx = num_ctx
        self.max_tokens = max_tokens
        self._ok_until = 0.0

    # --- HTTP -------------------------------------------------------------
    def _request(self, path: str, body: dict) -> urllib.request.Request:
        return urllib.request.Request(
            self.url + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
        )

    def _open(self, req: urllib.request.Request, timeout: float):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
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
            with urllib.request.urlopen(urllib.request.Request(self.url + "/api/tags"), timeout=2) as r:
                names = {m.get("name", "") for m in json.loads(r.read().decode()).get("models", [])}
        except Exception:
            return False
        ok = self.model in names or f"{self.model}:latest" in names
        if ok:
            self._ok_until = now + 30
        return ok

    def warmup(self) -> None:
        """Modeli belleğe yükler (boş istem); ilk kullanıcı yükleme süresini beklemesin."""
        body = {"model": self.model, "prompt": "", "keep_alive": self.keep_alive}
        with self._open(self._request("/api/generate", body), self.timeout) as r:
            r.read()

    # --- Üretim -----------------------------------------------------------
    def _body(
        self, system: str, turns: list[ChatTurn], stream: bool, max_tokens: int | None, temperature: float,
        num_ctx: int | None = None,
    ) -> dict:
        body = {
            "model": self.model,
            "stream": stream,
            "keep_alive": self.keep_alive,
            "messages": [{"role": "system", "content": system}] + [{"role": t.role, "content": t.content} for t in turns],
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens or self.max_tokens,
                "num_ctx": num_ctx or self.num_ctx,
            },
        }
        if self.logprobs:
            body["logprobs"] = True  # destekleyen sürümlerde token başına log-olasılık döner
        return body

    @staticmethod
    def _finish(text: str, lps: list[float], last: dict, t0: float) -> Generation:
        return Generation(
            text=text.strip(),
            mean_token_prob=math.exp(sum(lps) / len(lps)) if lps else None,
            min_token_prob=math.exp(min(lps)) if lps else None,
            seconds=time.time() - t0,
            tokens=int(last.get("eval_count") or len(lps)),
            prompt_tokens=int(last.get("prompt_eval_count") or 0),
            load_s=_ns(last, "load_duration"),
            prefill_s=_ns(last, "prompt_eval_duration"),
            decode_s=_ns(last, "eval_duration"),
            raw=last,
        )

    @staticmethod
    def _logprobs(d: dict) -> list[float]:
        return [x["logprob"] for x in (d.get("logprobs") or []) if isinstance(x, dict) and "logprob" in x]

    def generate(
        self, system: str, turns: list[ChatTurn], max_tokens: int | None = None, temperature: float = 0.2,
        num_ctx: int | None = None,
    ) -> Generation:
        t0 = time.time()
        body = self._body(system, turns, False, max_tokens, temperature, num_ctx)
        with self._open(self._request("/api/chat", body), max(self.timeout, 300)) as r:
            data = json.loads(r.read().decode())
        return self._finish((data.get("message") or {}).get("content", ""), self._logprobs(data), data, t0)

    def stream(
        self, system: str, turns: list[ChatTurn], max_tokens: int | None = None, temperature: float = 0.2
    ) -> Iterator[str | Generation]:
        """Cevabı parça parça üretir: önce metin parçaları (str), en sonda Generation."""
        t0 = time.time()
        text, lps, last = "", [], {}
        with self._open(self._request("/api/chat", self._body(system, turns, True, max_tokens, temperature)), self.timeout) as r:
            for line in r:
                if not line.strip():
                    continue
                d = json.loads(line.decode())
                if d.get("error"):
                    raise DecoderUnavailable(str(d["error"]))
                piece = (d.get("message") or {}).get("content", "")
                lps += self._logprobs(d)
                if piece:
                    text += piece
                    yield piece
                if d.get("done"):
                    last = d
                    break
        yield self._finish(text, lps, last, t0)


@lru_cache
def _client() -> OllamaDecoder | None:
    s = get_settings()
    if s.decoder != "ollama":
        return None
    return OllamaDecoder(
        s.decoder_url, s.decoder_model, s.decoder_timeout, s.decoder_logprobs,
        s.decoder_keep_alive, s.decoder_num_ctx, s.decoder_max_tokens,
    )


def get_decoder() -> OllamaDecoder | None:
    """Kullanılabilir decoder'ı döndürür; kapalı/yapılandırılmamışsa None."""
    c = _client()
    return c if c is not None and c.available() else None


def warmup_in_background() -> None:
    """Uygulama açılışında modeli arka planda belleğe yükler; açılışı bekletmez."""
    c = _client()
    if c is None or not get_settings().decoder_warmup:
        return

    def run():
        try:
            if c.available():
                c.warmup()
        except Exception:
            pass

    threading.Thread(target=run, daemon=True).start()
