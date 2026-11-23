"""Görevleri iş alanlarına kümeleme (HDBSCAN) ve kümeleri adlandırma (c-TF-IDF).

- Küme sayısı önceden verilmez; yoğunluğa göre bulunur.
- Hiçbir kümeye girmeyen görevler (etiket -1) aykırıdır: ekipte benzeri yapılmamış,
  alışılmadık işler. Bunlar liderin daha dikkatli bakması gereken görevlerdir.
- Az sayıda görevde (ör. tek doküman) kümeleme anlamsızdır; bu yüzden yeni görevler
  ekibin geçmiş görevleriyle birlikte kümelenir.
"""
from __future__ import annotations

import math
import re
import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass

import numpy as np
from sklearn.cluster import HDBSCAN

STOPWORDS = {
    "için", "ile", "gibi", "olan", "olarak", "daha", "sonra", "önce", "bir", "iki", "üç", "çok", "az",
    "ama", "fakat", "ancak", "veya", "ile", "bu", "şu", "o", "her", "tüm", "yeni", "eski", "kısa",
    "göre", "kadar", "üzere", "dair", "ise", "hem", "de", "da", "ki", "mi", "ve", "the", "and",
    "gerekiyor", "gerekir", "şart", "yapılacak", "edilecek", "düşüyor", "yaz", "taşı",
    "üzerine", "üzerinde", "tarafında", "tarafı", "sonrası", "geçen", "bazı", "hâlâ", "hala", "şu", "an",
    "bir", "ara", "bakabilir", "kontrol", "etsin", "olabilir", "kadar", "beraber",
}
WORD = re.compile(r"[a-zçğıöşü0-9]+", re.IGNORECASE)
STEM_LEN = 5  # Türkçe eklemeli: kaba kök için ilk 5 harf


@dataclass
class ClusterResult:
    labels: np.ndarray  # her öğe için küme no; -1 = hiçbir iş alanına girmedi (HDBSCAN gürültüsü)
    names: dict[int, str]  # küme no -> okunur ad
    outliers: np.ndarray  # gerçekten alışılmadık: en yakın komşusu bile çok uzak (robust z-skor)


def _tr_lower(word: str) -> str:
    # "API", "SSL" gibi kısaltmalar İngilizce küçültülür ("apı" olmasın); diğerleri Türkçe kurala göre.
    if word.isupper() and len(word) > 1:
        return word.lower()
    return word.replace("I", "ı").replace("İ", "i").lower()


def _tokens(text: str) -> list[str]:
    out = []
    for w in (_tr_lower(x) for x in WORD.findall(text)):
        if len(w) < 3 or w in STOPWORDS or w.isdigit():
            continue
        if re.search(r"(meli|malı|melidir|malıdır)$", w):  # yükümlülük fiilleri ad taşımaz
            continue
        out.append(w)
    return out


def name_clusters(
    texts: list[str], labels: np.ndarray, top_n: int = 2, exclude: set[str] | None = None
) -> dict[int, str]:
    """c-TF-IDF: bir kümede sık geçen ama diğer kümelerde seyrek olan kökler.

    Bir kök, kümenin en az iki öğesinde geçmiyorsa ad olarak kullanılmaz (tek cümleye
    özgü kelimeler küme adı olamaz). Uygun kök yoksa küme adsız kalır.
    """
    exclude = {e.lower()[:STEM_LEN] for e in (exclude or set())}
    stem_counts: dict[int, Counter] = defaultdict(Counter)
    surface: dict[str, Counter] = defaultdict(Counter)  # kök -> görülen kelime biçimleri
    doc_freq: dict[int, Counter] = defaultdict(Counter)  # kök kümenin kaç öğesinde geçiyor
    for text, lab in zip(texts, labels):
        if lab < 0:
            continue
        seen = set()
        for w in _tokens(text):
            stem = w[:STEM_LEN]
            if stem in exclude:
                continue
            stem_counts[int(lab)][stem] += 1
            surface[stem][w] += 1
            seen.add(stem)
        for stem in seen:
            doc_freq[int(lab)][stem] += 1
    if not stem_counts:
        return {}
    n_clusters = len(stem_counts)
    df = Counter(stem for c in stem_counts.values() for stem in c)
    names: dict[int, str] = {}
    for lab, counts in stem_counts.items():
        total = sum(counts.values()) or 1
        scored = sorted(
            [st for st in counts if doc_freq[lab][st] >= 2],
            key=lambda s: (counts[s] / total) * math.log(1 + n_clusters / df[s]),
            reverse=True,
        )
        words = [surface[s].most_common(1)[0][0] for s in scored[:top_n]]
        if words:
            names[lab] = " · ".join(words)
    return names


def nn_outliers(vecs: np.ndarray, z: float = 3.0) -> np.ndarray:
    """En yakın komşu benzerliği diğerlerine göre aşırı düşük olan öğeler (robust z-skor).

    HDBSCAN az sayıda noktada yalnız kalan bir öğeyi en yakın kümeye katabiliyor; bu
    ölçü onu tamamlar. Ölçekten bağımsızdır (medyan ve MAD), model değişse de çalışır.
    """
    sims = vecs @ vecs.T
    np.fill_diagonal(sims, -np.inf)
    nn = sims.max(axis=1)
    med = np.median(nn)
    mad = np.median(np.abs(nn - med)) * 1.4826 or 1e-6
    return (med - nn) / mad > z


def cluster(
    texts: list[str], vecs: np.ndarray, min_cluster_size: int = 2, exclude_words: set[str] | None = None
) -> ClusterResult:
    n = len(texts)
    if n < max(4, min_cluster_size * 2):
        return ClusterResult(np.full(n, -1), {}, np.zeros(n, dtype=bool))
    # min_samples = min_cluster_size: yalnız kalan noktalar kümeye zorla katılmaz, aykırı kalır
    model = HDBSCAN(min_cluster_size=max(2, min_cluster_size), metric="euclidean")
    # Vektörler L2-normalize: öklid mesafesi kosinüs benzerliğiyle aynı sıralamayı verir.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        labels = model.fit_predict(vecs)
    # İki ayrı kavram: HDBSCAN gürültüsü (-1) "belirgin bir iş alanına girmedi" demek;
    # "alışılmadık" ise benzeri hiç olmayan öğe. Ikincisi yalnızca komşu benzerliğinden gelir.
    outliers = nn_outliers(vecs)
    labels = np.where(outliers, -1, labels)
    return ClusterResult(labels, name_clusters(texts, labels, exclude=exclude_words), outliers)
