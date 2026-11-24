"""Görev tespiti için lineer probe eğitimi.

Encoder (embedding modeli) DONMUŞ kalır; üstüne yalnızca bir lojistik regresyon eğitilir:
    girdi  = [ cümle vektörü (ör. 384 boyut) ; Türkçe kip özellikleri (~15) ]
    çıktı  = p(görev)

Veri:
  - samples/train/*.tsv                  elle / Gemini / etiketleme aracı (her zaman eğitimde)
  - gorev_asistani.db                    liderin onay/ret kararları      (aktif öğrenme döngüsü)
  - app/ml/prototypes.py                 örnek ve zor negatif çiftler    (her zaman eğitimde)
  - samples/eval/*  + örnek notlar       doğrulama dokümanları           (çapraz doğrulamada dönüşümlü)
  - samples/test/*                       TEST — eğitime ve seçime HİÇ girmez

Model seçimi: doküman bazlı çapraz doğrulama (her seferinde bir doğrulama dokümanı dışarıda).
C (düzenlileştirme), karar eşiği ve yan cümle kullanımı F2 skoruna göre seçilir
(F2 duyarlılığı daha ağır tartar: kaçırılan görev, fazladan öneriden daha pahalı).

Kullanım (backend klasöründen):
    python scripts/train_probe.py                   # varsayılan embedding modeli
    python scripts/train_probe.py --model hashing   # indirmesiz hızlı deneme
Sonra: python scripts/evaluate.py --verbose
"""
import argparse
import re
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ROOT = Path(__file__).resolve().parents[2]


def _test_texts() -> list[str]:
    """Test dokümanlarının metinleri: bunlarla örtüşen hiçbir cümle eğitime girmez."""
    from app.services.documents import extract_text

    out = []
    tdir = ROOT / "samples" / "test"
    if (tdir / "gold.json").exists():
        for name in json.loads((tdir / "gold.json").read_text(encoding="utf-8")):
            if not name.startswith("_") and (tdir / name).exists():
                out.append(extract_text(name, (tdir / name).read_bytes()))
    return out


def load_db_labels(db_path: Path, test_texts: list[str]) -> tuple[list[str], list[int]]:
    """Uygulamadaki lider kararları -> etiket (aktif öğrenme döngüsü).

    1: onaylanan / aktarılan / tamamlanan görevler ve "görev" denen adaylar
    0: "görev değil" nedeniyle reddedilenler ve elenen adaylar
    "görev ama şimdi değil" reddi ve nedeni bilinmeyen eski retler etiket sayılmaz.
    """
    import sqlite3

    if not db_path.exists():
        return [], []
    con = sqlite3.connect(db_path)
    cols = {r[1] for r in con.execute("PRAGMA table_info(tasks)")}
    reason = "reject_reason" if "reject_reason" in cols else "NULL"
    rows = con.execute(
        f"SELECT source_quote, status, {reason} FROM tasks WHERE document_id IS NOT NULL AND source_quote != ''"
    ).fetchall()
    X, y, leaked = [], [], 0
    for quote, status, why in rows:
        if any(quote in t for t in test_texts):
            leaked += 1
            continue
        if status in ("accepted", "exported", "done"):
            X.append(quote); y.append(1)
        elif status == "dismissed" or (status == "rejected" and why == "not_task"):
            X.append(quote); y.append(0)
    if leaked:
        print(f"  (veritabanında test dokümanlarına ait {leaked} karar eğitimden çıkarıldı)")
    return X, y


_LABEL_FIRST = re.compile(r"^\s*([01])\s*[\t;|,]?\s+(.+?)\s*$")
_LABEL_LAST = re.compile(r"^\s*(.+?)\s*[\t;|,]?\s+([01])\s*$")


def parse_line(line: str) -> tuple[str, str] | None:
    """Etiketli satır: "1<TAB>cümle" (etiketleme aracı) ya da "cümle<TAB>1" (Gemini çıktısı).
    Kopyalarken TAB boşluğa dönüşmüş olabilir; tırnak ve madde işareti temizlenir."""
    if not line.strip() or line.lstrip().startswith("#"):
        return None
    if "\t" in line:
        a, b = line.split("\t", 1)
        a, b = a.strip(), b.strip()
        if a in ("0", "1"):
            lab, text = a, b
        elif b in ("0", "1"):
            lab, text = b, a
        else:
            return None
    else:
        m = _LABEL_FIRST.match(line) or None
        if m:
            lab, text = m.group(1), m.group(2)
        else:
            m = _LABEL_LAST.match(line)
            if not m:
                return None
            text, lab = m.group(1), m.group(2)
    text = re.sub(r"^\s*(?:[-•*]|\d+[.)])\s+", "", text).strip().strip('"“”\'').strip()
    return (lab, text) if len(text) >= 8 else None


def load_base(db_path: Path | None = None) -> tuple[list[str], list[int]]:
    from app.ml.prototypes import MODALITY_PAIRS, NON_TASK_EXAMPLES, TASK_EXAMPLES

    test_texts = _test_texts()
    X, y = [], []
    for f in sorted((ROOT / "samples" / "train").glob("*.tsv")):
        n = 0
        for line in f.read_text(encoding="utf-8-sig").splitlines():
            parsed = parse_line(line)
            if parsed is None:
                continue
            lab, text = parsed
            if any(text in t for t in test_texts):
                continue
            X.append(text)
            y.append(int(lab))
            n += 1
        print(f"  {f.name}: {n} cümle")
    if db_path:
        dx, dy = load_db_labels(db_path, test_texts)
        print(f"  uygulama kararları ({db_path.name}): {len(dx)} cümle")
        X += dx
        y += dy
    X += TASK_EXAMPLES + [a for a, _ in MODALITY_PAIRS]
    y += [1] * (len(TASK_EXAMPLES) + len(MODALITY_PAIRS))
    X += NON_TASK_EXAMPLES + [b for _, b in MODALITY_PAIRS]
    y += [0] * (len(NON_TASK_EXAMPLES) + len(MODALITY_PAIRS))
    # Tekrarları çıkar (aynı cümle iki kaynaktan gelirse son etiket geçerli)
    seen: dict[str, int] = {}
    for text, lab in zip(X, y):
        seen[text] = lab
    return list(seen), list(seen.values())


def load_validation_docs() -> list[tuple[str, list[str], list[int]]]:
    """[(doküman adı, cümleler, etiketler)] — doğrulama dokümanları."""
    from app.llm.text import split_sentences
    from app.seed import SPRINT_NOTE

    docs = [
        ("sprint14", SPRINT_NOTE, ["tek bir servise taşınmalı", "Face ID", "regresyon testinden", "maskelenmeli", "ölçekleme kuralı eklenmeli", "bilgilendirme metni"]),
        ("sprint15", (ROOT / "samples" / "sprint15-planlama.txt").read_text(encoding="utf-8"), ["sayfalama", "çöküyor", "15 dakikaya", "yük testi", "devreye alınmalı"]),
    ]
    gold = json.loads((ROOT / "samples" / "eval" / "gold.json").read_text(encoding="utf-8"))
    for name, positives in gold.items():
        if not name.startswith("_"):
            docs.append((name, (ROOT / "samples" / "eval" / name).read_text(encoding="utf-8"), positives))
    out = []
    for name, text, positives in docs:
        sents = [s.text for s in split_sentences(text)]
        out.append((name, sents, [int(any(p in s for p in positives)) for s in sents]))
    return out


def build_matrix(embedder, sentences: list[str]) -> np.ndarray:
    from app.ml.features import feature_matrix

    return np.hstack([embedder.encode(sentences), feature_matrix(sentences)])


def fit(Xm, y, C):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    clf = make_pipeline(StandardScaler(), LogisticRegression(C=C, class_weight="balanced", max_iter=5000))
    return clf.fit(Xm, y)


def sentence_scores(clf, embedder, sentences: list[str], use_clauses: bool) -> np.ndarray:
    from app.ml.features import clauses

    if not use_clauses:
        return clf.predict_proba(build_matrix(embedder, sentences))[:, 1]
    items, owner = [], []
    for i, s in enumerate(sentences):
        parts = clauses(s)
        for t in [s] + (parts if len(parts) > 1 else []):
            items.append(t)
            owner.append(i)
    probs = clf.predict_proba(build_matrix(embedder, items))[:, 1]
    out = np.zeros(len(sentences))
    for i, pr in zip(owner, probs):
        out[i] = max(out[i], pr)
    return out


def prf(y, pred, beta=2.0):
    y, pred = np.asarray(y), np.asarray(pred)
    tp = int(((y == 1) & (pred == 1)).sum())
    fp = int(((y == 0) & (pred == 1)).sum())
    fn = int(((y == 1) & (pred == 0)).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    fb = (1 + beta**2) * p * r / (beta**2 * p + r) if p + r else 0.0
    return p, r, f1, fb


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)

    def flush(self):
        for st in self.streams:
            st.flush()


def _setup_output(out: str | None) -> None:
    # Windows konsolu (cp1254) "→", "−" gibi karakterlerde çöker: çıktıyı UTF-8'e zorla.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if out:
        sys.stdout = _Tee(sys.stdout, open(out, "w", encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None, help="GA_EMBED_MODEL değeri")
    ap.add_argument("--db", default="gorev_asistani.db", help="lider kararlarının okunacağı veritabanı ('' = kullanma)")
    ap.add_argument("--out", default=None, help="çıktıyı UTF-8 olarak bu dosyaya da yaz")
    a = ap.parse_args()
    _setup_output(a.out)
    if a.model:
        os.environ["GA_EMBED_MODEL"] = a.model

    from app.config import get_settings
    from app.ml.embedder import get_embedder

    embedder = get_embedder()
    print("Eğitim verisi:")
    base_X, base_y = load_base(Path(a.db) if a.db else None)
    vdocs = load_validation_docs()
    print(f"Embedding modeli: {embedder.name}")
    print(f"Temel eğitim: {len(base_X)} cümle ({sum(base_y)} görev) · doğrulama: {len(vdocs)} doküman, "
          f"{sum(len(d[1]) for d in vdocs)} cümle ({sum(sum(d[2]) for d in vdocs)} görev)")

    base_M = build_matrix(embedder, base_X)
    doc_M = [build_matrix(embedder, d[1]) for d in vdocs]

    # Doküman bazlı çapraz doğrulama: her doğrulama dokümanı bir kez dışarıda
    results = []
    for C in (0.01, 0.03, 0.1, 0.3, 1.0):
        for use_clauses in (False, True):
            ys, ps = [], []
            for k, (name, sents, labels) in enumerate(vdocs):
                tr_M = np.vstack([base_M] + [doc_M[j] for j in range(len(vdocs)) if j != k])
                tr_y = base_y + [l for j, d in enumerate(vdocs) if j != k for l in d[2]]
                clf = fit(tr_M, tr_y, C)
                ps.extend(sentence_scores(clf, embedder, sents, use_clauses))
                ys.extend(labels)
            ps = np.array(ps)
            for thr in np.arange(0.2, 0.81, 0.05):
                p, r, f1, f2 = prf(ys, (ps >= thr).astype(int))
                results.append((f2, f1, p, r, C, use_clauses, round(float(thr), 2)))
    results.sort(key=lambda x: (x[0], x[1]), reverse=True)
    f2, f1, p, r, C, use_clauses, thr = results[0]
    print("\nÇapraz doğrulama (dışarıda bırakılan dokümanlarda), en iyi 5 ayar:")
    print(f"  {'F2':>5} {'F1':>5} {'kes.':>5} {'duy.':>5}   C      yan_cümle  eşik")
    for row in results[:5]:
        print(f"  {row[0]:5.2f} {row[1]:5.2f} {row[2]:5.2f} {row[3]:5.2f}   {row[4]:<6} {str(row[5]):<10} {row[6]}")

    # Seçilen ayarla tüm eğitim + doğrulama verisinde son model
    all_M = np.vstack([base_M] + doc_M)
    all_y = base_y + [l for d in vdocs for l in d[2]]
    clf = fit(all_M, all_y, C)

    import joblib

    from app.ml.features import FEATURE_NAMES

    path = Path(get_settings().probe_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "classifier": clf,
            "embed_model": embedder.name,
            "threshold": thr,
            "use_clauses": use_clauses,
            "feature_names": FEATURE_NAMES,
            "cv": {"f2": f2, "f1": f1, "precision": p, "recall": r, "C": C},
        },
        path,
    )

    # Hangi kip özelliği ne yönde etkili? (standartlaştırılmış katsayılar)
    coefs = clf[-1].coef_[0][-len(FEATURE_NAMES):]
    print("\nKip özelliklerinin etkisi (+ görev yönünde, − görev değil yönünde):")
    for n, c in sorted(zip(FEATURE_NAMES, coefs), key=lambda x: -abs(x[1])):
        print(f"  {n:<14} {c:+.2f}")
    print(f"\nKaydedildi: {path}  (eşik={thr}, yan_cümle={use_clauses}, C={C})")
    print("Test setindeki başarı için: python scripts/evaluate.py --verbose")


if __name__ == "__main__":
    main()
