"""Encoder tabanlı sağlayıcı (eğitimsiz).

Önceden eğitilmiş, dondurulmuş bir cümle-embedding modeli kullanır:
  1. Doküman cümlelere bölünür, her cümlenin vektörü çıkarılır.
  2. Görev mi? İki sinyal birleşir:
     a) Kip yönü: konu aynı/kip farklı cümle çiftlerinden "yapılacak ↔ yapıldı" yönü
        (ortalama farkı) çıkarılır; cümlenin bu yöndeki standartlaştırılmış izdüşümü.
     b) Prototip benzerliği: en yakın görev / görev olmayan örneklere benzerlik farkı.
  3. Alan etiketi -> etiket açıklamalarına benzerlik.
Metin üretimi yapılmaz; başlık cümleden türetilir. Kısa başlık üretimi sonraki aşamadır.
"""
from pathlib import Path

import numpy as np

from ..config import get_settings
from ..ml.embedder import Embedder, get_embedder
from ..ml.features import clauses, feature_matrix
from ..ml.prototypes import MODALITY_PAIRS, NON_TASK_EXAMPLES, TAG_DESCRIPTIONS, TASK_EXAMPLES
from .base import ChatTurn, ExtractedTask
from .mock import MockProvider
from .text import spoken_commitment, OBLIGATION, estimate_days, split_sentences, title_from

TOP_K = 3
SHARPNESS = 20.0  # benzerlik farkını logit ölçeğine çeviren eğim
RULE_PRIOR = 0.04  # yükümlülük kipi ("-meli") varsa küçük bir öncül katkı (benzerlik ölçeğinde)
W_DIRECTION = 1.0  # kip yönü skorunun (z) logit'e katkısı
W_PROTOTYPE = 0.5  # prototip benzerliğinin logit'e katkısı
THRESHOLD = 0.5


def _topk_mean(sims: np.ndarray, k: int) -> np.ndarray:
    k = min(k, sims.shape[1])
    return np.sort(sims, axis=1)[:, -k:].mean(axis=1)


class EncoderProvider:
    name = "encoder"

    def __init__(self, embedder: Embedder | None = None, use_probe: bool = True):
        self.embedder = embedder or get_embedder()
        self.probe = self._load_probe() if use_probe else None
        pair_task = self.embedder.encode([a for a, _ in MODALITY_PAIRS])
        pair_stat = self.embedder.encode([b for _, b in MODALITY_PAIRS])
        self._pos = np.vstack([self.embedder.encode(TASK_EXAMPLES), pair_task])
        self._neg = np.vstack([self.embedder.encode(NON_TASK_EXAMPLES), pair_stat])

        # Kip yönü (difference of means) ve ölçeği
        d = pair_task.mean(axis=0) - pair_stat.mean(axis=0)
        self._dir = d / (np.linalg.norm(d) or 1.0)
        pt, ps = pair_task @ self._dir, pair_stat @ self._dir
        self._mid = float((pt.mean() + ps.mean()) / 2)
        self._scale = float((pt.std() + ps.std()) / 2) or 1e-6
        self._tag_names = list(TAG_DESCRIPTIONS)
        cents = []
        for tag in self._tag_names:
            v = self.embedder.encode(TAG_DESCRIPTIONS[tag]).mean(axis=0)
            cents.append(v / (np.linalg.norm(v) or 1.0))
        self._tags = np.stack(cents)

    def _load_probe(self):
        path = Path(get_settings().probe_path)
        if not path.exists():
            return None
        import joblib

        probe = joblib.load(path)
        if probe.get("embed_model") != self.embedder.name:
            return None  # başka bir embedding modeliyle eğitilmiş: kullanılamaz
        return probe

    @property
    def method(self) -> str:
        return "probe" if self.probe else "prototip"

    def _probe_scores(self, sentences: list[str]) -> np.ndarray:
        clf = self.probe["classifier"]
        if not self.probe.get("use_clauses"):
            m = np.hstack([self.embedder.encode(sentences), feature_matrix(sentences)])
            return clf.predict_proba(m)[:, 1]
        # Cümleler ve yan cümleleri TEK seferde kodla (her cümle için ayrı çağrı çok yavaş)
        items: list[str] = []
        owner: list[int] = []
        for i, s in enumerate(sentences):
            parts = clauses(s)
            for t in [s] + (parts if len(parts) > 1 else []):
                items.append(t)
                owner.append(i)
        m = np.hstack([self.embedder.encode(items), feature_matrix(items)])
        probs = clf.predict_proba(m)[:, 1]
        out = np.zeros(len(sentences))
        for i, pr in zip(owner, probs):
            out[i] = max(out[i], pr)
        return out

    def task_scores(self, sentences: list[str]) -> np.ndarray:
        if not sentences:
            return np.zeros(0)
        if self.probe:
            return self._probe_scores(sentences)
        e = self.embedder.encode(sentences)
        margin = _topk_mean(e @ self._pos.T, TOP_K) - _topk_mean(e @ self._neg.T, TOP_K)
        prior = np.array([RULE_PRIOR if OBLIGATION.search(s) else 0.0 for s in sentences])
        z = (e @ self._dir - self._mid) / self._scale  # kip yönündeki konum, standart sapma biriminde
        logit = W_DIRECTION * z + W_PROTOTYPE * SHARPNESS * margin + SHARPNESS * prior
        return 1.0 / (1.0 + np.exp(-logit))

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
        threshold = self.probe["threshold"] if self.probe else THRESHOLD
        # Toplantı dökümünde konuşanın birinci şahısla iş üstlenmesi ("bunu ben düzeltirim") güçlü
        # bir dil sinyali; eğitim verisi yazılı metin ağırlıklı olduğu için model bunu zayıf görebilir.
        committed = {i for i, s in enumerate(sents) if spoken_commitment(document_text, s.text, s.start)}
        scores = [max(float(p), threshold) if i in committed else p for i, p in enumerate(scores)]
        low = threshold - get_settings().candidate_margin
        keep = [i for i, p in enumerate(scores) if p >= low]
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
                candidate=bool(scores[i] < threshold),
            )
            for i, tag in zip(keep, tags)
        ]

    def chat(self, turns: list[ChatTurn], context: str) -> str:
        return MockProvider().chat(turns, context)
