"""Yüklenen dosyalardan düz metin çıkarma (tamamen yerel)."""
import io

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
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if name.endswith(".docx"):
        doc = DocxDocument(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    raise UnsupportedFile(f"Desteklenmeyen dosya türü. Desteklenenler: {', '.join(SUPPORTED)}")
