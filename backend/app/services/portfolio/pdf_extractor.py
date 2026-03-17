from __future__ import annotations

from typing import BinaryIO

from pypdf import PdfReader


def extract_text_from_pdf_stream(stream: BinaryIO) -> str:
    """Extract text from a PDF binary stream."""
    reader = PdfReader(stream)
    parts: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text:
            parts.append(text)
    return "\n\n".join(parts)

