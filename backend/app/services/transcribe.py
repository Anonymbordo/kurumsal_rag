"""Konuşmayı yazıya dökme (ASR), CPU'da.

faster-whisper: OpenAI Whisper'ın CTranslate2 ile yeniden derlenmiş hali. Whisper da bir
encoder-decoder transformer: encoder log-mel spektrogramı temsillere çevirir, decoder bu
temsillere çapraz dikkatle (cross-attention) bakarak metni token token üretir.
int8 kuantizasyonla CPU'da çalışır; ses kurum dışına çıkmaz.

Model ilk kullanımda indirilir (small ≈ 470 MB) ve önbellekte tutulur.
"""
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from ..config import get_settings


@dataclass
class Segment:
    start: float  # saniye, kayıt başına göre
    end: float
    text: str


class Transcriber(Protocol):
    name: str

    def transcribe(self, path: str, prompt: str = "") -> list[Segment]: ...


class TranscriberUnavailable(RuntimeError):
    pass


SAMPLE_RATE = 16000


def decode_audio(path: str):
    """Sesi 16 kHz mono float32 diziye çevirir (PyAV ile).

    faster-whisper'ın kendi çözücüsü bazı PyAV sürümlerinde kırılıyor (av.open'a
    artık desteklenmeyen 'metadata_errors' parametresini veriyor); bu yüzden ses
    burada çözülüp modele hazır dizi olarak verilir. Bozuk parçalar atlanır.
    """
    import av
    import numpy as np

    resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    parts = []
    with av.open(path, mode="r") as container:
        if not container.streams.audio:
            raise TranscriberUnavailable("Dosyada ses kanalı yok")
        for frame in container.decode(audio=0):
            try:
                out = resampler.resample(frame)
            except Exception:  # noqa: BLE001 — bozuk çerçeve
                continue
            for f in out if isinstance(out, list) else [out]:
                if f is not None:
                    parts.append(f.to_ndarray().reshape(-1))
        try:
            tail = resampler.resample(None)  # içerde kalan örnekler
            for f in tail if isinstance(tail, list) else [tail]:
                if f is not None:
                    parts.append(f.to_ndarray().reshape(-1))
        except Exception:  # noqa: BLE001
            pass
    if not parts:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(parts).astype(np.float32) / 32768.0


class FasterWhisper:
    def __init__(self, model: str, compute_type: str, language: str, beam_size: int = 5):
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:  # isteğe bağlı bağımlılık
            raise TranscriberUnavailable(
                "faster-whisper kurulu değil: pip install -r requirements-asr.txt"
            ) from e
        self.name = f"faster-whisper {model} ({compute_type})"
        self.language = language
        self.beam_size = beam_size
        self.model = WhisperModel(model, device="cpu", compute_type=compute_type)

    def transcribe(self, path: str, prompt: str = "") -> list[Segment]:
        """`prompt`: kurum terimleri ve katılımcı adları. Whisper'ın decoder'ı bunu önceki bağlam
        sayar; "deploy", "regresyon", kişi adları gibi kelimeleri doğru yazma olasılığı artar."""
        audio = decode_audio(path)
        if audio.size < SAMPLE_RATE // 2:  # yarım saniyeden kısa: konuşma yok
            return []
        segments, _ = self.model.transcribe(
            audio,
            language=self.language,
            vad_filter=True,  # sessizliği atla: hem hız hem "sessizlikte uydurma" önlemi
            beam_size=self.beam_size,  # toplantı sonrası arka planda çalıştığı için kalite öncelikli
            condition_on_previous_text=False,  # tekrar döngülerini (halüsinasyon) azaltır
            initial_prompt=prompt or None,
        )
        return [Segment(s.start, s.end, s.text.strip()) for s in segments if s.text.strip()]


@lru_cache
def get_transcriber() -> Transcriber:
    s = get_settings()
    return FasterWhisper(s.whisper_model, s.whisper_compute, s.whisper_language, s.whisper_beam_size)
