"""Wrapper sobre `docling` para convertir PDFs a markdown.

Se aisla detras de un Protocol para poder mockear en tests sin instalar
docling completo en CI.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Protocol


class PdfToMarkdownConverter(Protocol):
    def convert_to_markdown(self, pdf_path: Path) -> str:
        ...


class DoclingPdfConverter:
    """Implementacion real usando docling."""

    def __init__(self) -> None:
        from docling.document_converter import DocumentConverter

        self._converter = DocumentConverter()

    def convert_to_markdown(self, pdf_path: Path) -> str:
        result = self._converter.convert(str(pdf_path))
        return result.document.export_to_markdown()


_lock = threading.Lock()
_shared_docling: DoclingPdfConverter | None = None


def get_docling_pdf_converter() -> DoclingPdfConverter:
    """Reutiliza un `DocumentConverter` por proceso (evitar cold-start en cada POST)."""
    global _shared_docling
    if _shared_docling is not None:
        return _shared_docling
    with _lock:
        if _shared_docling is None:
            _shared_docling = DoclingPdfConverter()
        return _shared_docling
