"""Görev çıkarma değerlendirmesi: kural tabanlı (mock) ile encoder'ı karşılaştırır.

Kullanım (backend klasöründen):
    python scripts/evaluate.py                     # varsayılan embedding modeliyle
    python scripts/evaluate.py --model hashing     # indirme yapmadan hızlı deneme
    python scripts/evaluate.py --model intfloat/multilingual-e5-base --verbose

Altın etiketler: hangi cümlenin gerçekten görev olduğu (elle işaretlendi).
Yeni doküman ve etiket ekledikçe ölçüm anlamlılaşır.
"""
import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ROOT = Path(__file__).resolve().parents[2]

# (doküman, [görev cümlelerinden ayırt edici parça, ...])
GOLD: list[tuple[str, list[str]]] = []


def _load_gold():
    from app.seed import SPRINT_NOTE

    GOLD.append(
        (
            SPRINT_NOTE,
            ["tek bir servise taşınmalı", "Face ID", "regresyon testinden", "maskelenmeli", "ölçekleme kuralı eklenmeli", "bilgilendirme metni"],
        )
    )
    s15 = (ROOT / "samples" / "sprint15-planlama.txt").read_text(encoding="utf-8")
    GOLD.append((s15, ["sayfalama", "çöküyor", "15 dakikaya", "yük testi", "devreye alınmalı"]))


def evaluate(provider, verbose=False):
    from app.llm.text import split_sentences

    tp = fp = fn = 0
    for text, positives in GOLD:
        found = {t.source_quote for t in provider.extract_tasks(text, "meeting")}
        for s in split_sentences(text):
            gold = any(p in s.text for p in positives)
            pred = s.text in found
            tp += gold and pred
            fp += (not gold) and pred
            fn += gold and not pred
            if verbose and gold != pred:
                print(f"   {'KAÇIRDI ' if gold else 'FAZLADAN'} | {s.text[:90]}")
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None, help="GA_EMBED_MODEL değeri")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    if a.model:
        os.environ["GA_EMBED_MODEL"] = a.model
    _load_gold()

    from app.llm.encoder import EncoderProvider
    from app.llm.mock import MockProvider

    print(f"{'sağlayıcı':<40} kesinlik  duyarlılık  F1")
    for name, factory in (("mock (kural tabanlı)", MockProvider), ("encoder", EncoderProvider)):
        t0 = time.perf_counter()
        prov = factory()
        load = time.perf_counter() - t0
        t0 = time.perf_counter()
        p, r, f1 = evaluate(prov, a.verbose)
        dt = time.perf_counter() - t0
        label = name if name.startswith("mock") else f"encoder ({prov.embedder.name})"
        print(f"{label:<40} {p:8.2f}  {r:10.2f}  {f1:4.2f}   yükleme {load:.1f}s, çıkarım {dt*1000:.0f}ms")


if __name__ == "__main__":
    main()
