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

# küme adı -> [(doküman adı, metin, [görev cümlelerinden ayırt edici parça, ...])]
SETS: dict[str, list[tuple[str, str, list[str]]]] = {}


def _load_gold():
    import json

    GOLD: list = []
    SETS["kolay (örnek notlar)"] = GOLD
    from app.seed import SPRINT_NOTE

    GOLD.append(
        (
            "sprint14",
            SPRINT_NOTE,
            ["tek bir servise taşınmalı", "Face ID", "regresyon testinden", "maskelenmeli", "ölçekleme kuralı eklenmeli", "bilgilendirme metni"],
        )
    )
    s15 = (ROOT / "samples" / "sprint15-planlama.txt").read_text(encoding="utf-8")
    GOLD.append(("sprint15", s15, ["sayfalama", "çöküyor", "15 dakikaya", "yük testi", "devreye alınmalı"]))

    hard = []
    gold = json.loads((ROOT / "samples" / "eval" / "gold.json").read_text(encoding="utf-8"))
    for name, positives in gold.items():
        if name.startswith("_"):
            continue
        hard.append((name, (ROOT / "samples" / "eval" / name).read_text(encoding="utf-8"), positives))
    SETS["zor (gerçekçi yazım) · doğrulama"] = hard

    from app.services.documents import extract_text

    test = []
    tdir = ROOT / "samples" / "test"
    if (tdir / "gold.json").exists():
        tgold = json.loads((tdir / "gold.json").read_text(encoding="utf-8"))
        for name, spec in tgold.items():
            if name.startswith("_"):
                continue
            text = extract_text(name, (tdir / name).read_bytes())
            test.append((name, text, spec))
    if test:
        SETS["TEST (bağımsız, dokunulmaz)"] = test


def evaluate(provider, docs, verbose=False):
    from app.llm.text import split_sentences

    tp = fp = fn = 0
    for name, text, spec in docs:
        positives = spec["tasks"] if isinstance(spec, dict) else spec
        ambiguous = spec.get("ambiguous", []) if isinstance(spec, dict) else []
        found = {t.source_quote for t in provider.extract_tasks(text, "meeting")}
        sents = split_sentences(text)
        missing = [p for p in positives if not any(p in s.text for s in sents)]
        if missing:
            print(f"   UYARI {name}: altın etiket cümlelerde bulunamadı: {missing}")
        for s in sents:
            if any(a in s.text for a in ambiguous):
                continue  # belirsiz cümleler puanlanmaz
            gold = any(p in s.text for p in positives)
            pred = s.text in found
            tp += gold and pred
            fp += (not gold) and pred
            fn += gold and not pred
            if verbose and gold != pred:
                print(f"   {'KAÇIRDI ' if gold else 'FAZLADAN'} | {name:<24} | {s.text[:80]}")
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

    provs = []
    for name, factory in (
        ("mock (kural tabanlı)", MockProvider),
        ("prototip", lambda: EncoderProvider(use_probe=False)),
        ("probe", EncoderProvider),
    ):
        t0 = time.perf_counter()
        prov = factory()
        if name == "probe" and prov.method != "probe":
            print("(eğitilmiş probe yok ya da başka modelle eğitilmiş: python scripts/train_probe.py)")
            continue
        label = name if name.startswith("mock") else f"{name} ({prov.embedder.name.split('/')[-1]})"
        provs.append((label, prov, time.perf_counter() - t0))

    for set_name, docs in SETS.items():
        n = sum(len(d[2]["tasks"] if isinstance(d[2], dict) else d[2]) for d in docs)
        print(f"\n== {set_name}: {len(docs)} doküman, {n} görev")
        if not set_name.startswith("TEST") and any(l.startswith("probe") for l, _, _ in provs):
            print("   (probe bu dokümanlarla EĞİTİLDİ; buradaki probe skoru iyimser. Dürüst doğrulama skoru"
                  " train_probe.py'nin çapraz doğrulama çıktısıdır.)")
        print(f"{'sağlayıcı':<44} kesinlik  duyarlılık  F1")
        for label, prov, load in provs:
            t0 = time.perf_counter()
            p, r, f1 = evaluate(prov, docs, a.verbose)
            dt = time.perf_counter() - t0
            print(f"{label:<44} {p:8.2f}  {r:10.2f}  {f1:4.2f}   çıkarım {dt*1000:.0f}ms (yükleme {load:.1f}s)")


if __name__ == "__main__":
    main()
