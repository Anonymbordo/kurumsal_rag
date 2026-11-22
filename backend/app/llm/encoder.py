"""Encoder tabanlı sağlayıcı (eğitimsiz).

Önceden eğitilmiş, dondurulmuş bir cümle-embedding modeli kullanır:
  1. Doküman cümlelere bölünür, her cümlenin vektörü çıkarılır.
  2. Görev mi? -> örnek görev / görev olmayan cümlelere benzerlik farkı (prototip sınıflandırma).
  3. Alan etiketi -> etiket açıklamalarına benzerlik.
Metin üretimi yapılmaz; başlık cümleden türetilir. Kısa başlık üretimi sonraki aşamadır.
"""
import numpy as np

from ..ml.embedder import Embedder, get_embedder
from ..ml.prototypes import NON_TASK_EXAMPLES, TAG_DESCRIPTIONS, TASK_EXAMPLES
from .base import ChatTurn, ExtractedTask
from .mock import MockProvider
from .text import OBLIGATION, estimate_days, split_sentences, title_from

TOP_K = 3
SHARPNESS = 20.0  # benzerlik farkını olasılığa çeviren eğim
RULE_PRIOR = 0.04  # yükümlülük kipi ("-meli") varsa küçük bir öncül katkı
THRESHOLD = 0.5


def _topk_mean(sims: np.ndarray, k: int) -> np.ndarray:
    k = min(k, sims.shape[1])
    return np.sort(sims, axis=1)[:, -k:].mean(axis=1)


class EncoderProvider:
    name = "encoder"

    def __init__(self, embedder: Embedder | None = None):
        self.embedder = embedder or get_embedder()
        self._pos = self.embedder.encode(TASK_EXAMPLES)
        self._neg = self.embedder.encode(NON_TASK_EXAMPLES)
        self._tag_names = list(TAG_DESCRIPTIONS)
        cents = []
        for tag in self._tag_names:
            v = self.embedder.encode(TAG_DESCRIPTIONS[tag]).mean(axis=0)
            cents.append(v / (np.linalg.norm(v) or 1.0))
        self._tags = np.stack(cents)

    def task_scores(self, sentences: list[str]) -> np.ndarray:
        if not sentences:
            return np.zeros(0)
        e = self.embedder.encode(sentences)
        margin = _topk_mean(e @ self._pos.T, TOP_K) - _topk_mean(e @ self._neg.T, TOP_K)
        prior = np.array([RULE_PRIOR if OBLIGATION.search(s) else 0.0 for s in sentences])
        return 1.0 / (1.0 + np.exp(-SHARPNESS * (margin + prior)))

    def tags_for(self, vecs: np.ndarray) -> list[list[str]]:
        out = []
        for row in vecs @ self._tags.T:
            order = np.argsort(row)[::-1]
            top = row[order[0]]
            if top - row.mean() < 0.02:
                out.append(["general"])
                continue
            tags = [self._tag_names[i] for i in order[:2] if row[i] >= top - 0.015]
            if "ios" in tags and "mobile" not in tags:
                tags.append("mobile")
            out.append(tags)
        return out

    def extract_tasks(self, document_text: str, doc_type: str) -> list[ExtractedTask]:
        sents = split_sentences(document_text)
        if not sents:
            return []
        texts = [s.text for s in sents]
        scores = self.task_scores(texts)
        keep = [i for i, p in enumerate(scores) if p >= THRESHOLD]
        if not keep:
            return []
        tags = self.tags_for(self.embedder.encode([texts[i] for i in keep]))
        return [
            ExtractedTask(
                title=title_from(sents[i].text),
                tags=tag,
                est_days=estimate_days(sents[i].text),
                source_ref=sents[i].ref,
                source_quote=sents[i].text,
                source_start=sents[i].start,
                source_end=sents[i].end,
                detect_score=float(scores[i]),
            )
            for i, tag in zip(keep, tags)
        ]

    def chat(self, turns: list[ChatTurn], context: str) -> str:
        return MockProvider().chat(turns, context)
