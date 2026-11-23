"""Etiketleme aracı: gerçek dokümanları eğitim ya da test verisine dönüştürür.

Akış: dosya/metin -> (isteğe bağlı) anonimleştirme -> cümlelere bölme -> lider her cümleyi
görev / değil / belirsiz diye işaretler -> samples/train veya samples/test'e yazılır.

Test için modelin tahmini GÖSTERİLMEZ (kör etiketleme); eğitim için gösterilir (hız için).
"""
import json
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..config import get_settings
from ..deps import require_lead
from ..llm import get_provider
from ..llm.text import split_sentences
from ..models import User
from ..services.anonymize import anonymize
from ..services.documents import UnsupportedFile, extract_text

router = APIRouter(prefix="/api/labeling", tags=["etiketleme"])


def _samples() -> Path:
    return Path(get_settings().samples_dir).resolve()


def _slug(title: str) -> str:
    t = title.lower().translate(str.maketrans("çğıöşü", "cgiosu"))
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")[:60] or "dokuman"


@router.post("/preview")
async def preview(
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    split: Literal["train", "test"] = Form(default="train"),
    names: str = Form(default=""),
    do_anonymize: bool = Form(default=True),
    user: User = Depends(require_lead),
):
    if file is not None:
        try:
            body = extract_text(file.filename or "", await file.read())
        except UnsupportedFile as e:
            raise HTTPException(415, str(e)) from e
        title = (file.filename or "doküman").rsplit(".", 1)[0]
    elif text:
        body, title = text, "yapistirilan_metin"
    else:
        raise HTTPException(400, "Dosya ya da metin gönderin")

    changes: dict[str, int] = {}
    if do_anonymize:
        body, changes = anonymize(body, [n for n in re.split(r"[,\n]", names) if n.strip()])

    sents = [s.text for s in split_sentences(body)]
    suggestions = None
    if split == "train":  # test için kör etiketleme: model tahmini gösterilmez
        prov = get_provider()
        if hasattr(prov, "task_scores"):
            suggestions = [round(float(p), 2) for p in prov.task_scores(sents)]
    return {"title": title, "text": body, "sentences": sents, "suggestions": suggestions, "anonymized": changes}


class SaveBody(BaseModel):
    title: str
    split: Literal["train", "test"]
    text: str
    sentences: list[str]
    labels: list[Literal["task", "not_task", "ambiguous"]]


@router.post("/save")
def save(body: SaveBody, user: User = Depends(require_lead)):
    if len(body.sentences) != len(body.labels):
        raise HTTPException(422, "Cümle ve etiket sayısı eşleşmiyor")
    root = _samples()
    slug = _slug(body.title)
    if body.split == "train":
        d = root / "train"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"etiket_{slug}.tsv"
        lines = ["# etiketleme aracıyla kaydedildi — 1: görev, 0: görev değil (belirsizler atlandı)"]
        lines += [f"{1 if l == 'task' else 0}\t{s}" for s, l in zip(body.sentences, body.labels) if l != "ambiguous"]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        d = root / "test"
        d.mkdir(parents=True, exist_ok=True)
        fname = f"{slug}.txt"
        (d / fname).write_text(body.text, encoding="utf-8")
        gold_path = d / "gold.json"
        gold = json.loads(gold_path.read_text(encoding="utf-8")) if gold_path.exists() else {}
        # Cümlenin tamamı ayırt edici parça olarak saklanır
        gold[fname] = {
            "tasks": [s for s, l in zip(body.sentences, body.labels) if l == "task"],
            "ambiguous": [s for s, l in zip(body.sentences, body.labels) if l == "ambiguous"],
        }
        gold_path.write_text(json.dumps(gold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        path = d / fname
    n_task = sum(l == "task" for l in body.labels)
    return {"saved": str(path.relative_to(root.parent)), "tasks": n_task, "sentences": len(body.sentences)}


@router.get("/stats")
def stats(user: User = Depends(require_lead)):
    root = _samples()
    train = 0
    for f in (root / "train").glob("*.tsv") if (root / "train").exists() else []:
        train += sum(1 for l in f.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#"))
    test_docs = 0
    g = root / "test" / "gold.json"
    if g.exists():
        test_docs = sum(1 for k in json.loads(g.read_text(encoding="utf-8")) if not k.startswith("_"))
    return {"train_sentences": train, "test_documents": test_docs}
