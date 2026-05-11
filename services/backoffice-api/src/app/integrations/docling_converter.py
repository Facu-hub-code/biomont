"""Wrapper sobre `docling` para convertir PDFs a markdown.

Se aisla detras de un Protocol para poder mockear en tests sin instalar
docling completo en CI.
"""

from __future__ import annotations

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
