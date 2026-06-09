"""Formato de texto para WhatsApp (negrita con un solo asterisco)."""

from __future__ import annotations

import re

_BOLD_DOUBLE = re.compile(r"\*\*(.+?)\*\*")


def wa_bold(text: str) -> str:
    """Negrita WhatsApp: *texto*."""
    return f"*{text}*"


def normalize_whatsapp_markdown(text: str) -> str:
    """Convierte **negrita** estilo Markdown a *negrita* de WhatsApp."""
    return _BOLD_DOUBLE.sub(r"*\1*", text)
