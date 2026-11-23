"""Yüklenen dosyalardan düz metin çıkarma (tamamen yerel)."""
import io
import re

from docx import Document as DocxDocument
from pypdf import PdfReader

SUPPORTED = (".txt", ".md", ".pdf", ".docx")


class UnsupportedFile(ValueError):
    pass


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith((".txt", ".md")):
        return data.decode("utf-8", errors="replace")
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return reflow("\n".join((page.extract_text() or "") for page in reader.pages))
    if name.endswith(".docx"):
        doc = DocxDocument(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    raise UnsupportedFile(f"Desteklenmeyen dosya türü. Desteklenenler: {', '.join(SUPPORTED)}")


_NEW_BLOCK = re.compile(r"^\s*(?:[-–•*▪●]|\d+[.)]|§|Madde\s+\d|[A-ZÇĞİÖŞÜ][^.!?]{0,60}:)")


def reflow(text: str) -> str:
    """PDF'in görsel satır kırılımlarını birleştirir; paragraf ve madde yapısını korur.

    PDF'ten çıkan metinde satırlar sayfa genişliğinde kırılır ("...servise\ntaşınmalı").
    Bir satır cümle sonu noktalamasıyla bitmiyorsa ve sonraki satır yeni bir madde /
    başlık değilse iki satır tek paragrafta birleştirilir.
    """
    lines = [l.rstrip() for l in text.replace("\r", "").split("\n")]
    out: list[str] = []
    for line in lines:
        if not line.strip():
            if out and out[-1] != "":
                out.append("")
            continue
        if out and out[-1] and not re.search(r"[.!?:]$", out[-1]) and not _NEW_BLOCK.match(line):
            prev = out[-1]
            out[-1] = prev[:-1] + line.lstrip() if prev.endswith("-") else prev + " " + line.strip()
        else:
            out.append(line.strip())
    return "\n".join(l for l in out if l != "")
