"""Extractor de FAQ del balotario via LLM (spec 003).

Una unica llamada por documento balotario (no por chunk): recibe el
markdown completo y devuelve la lista de pares (question, answer) con
schema estricto. Si falla, el ingest sigue (el balotario tambien queda
chunkificado normalmente para fallback).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from biomont_common.logging import get_logger

_logger = get_logger("etl.faq_extractor")


class FaqPair(BaseModel):
    """Una entrada del balotario."""

    question: str = Field(min_length=3)
    answer: str = Field(min_length=3)
    source_page: int | None = Field(default=None, ge=1)


class FaqList(BaseModel):
    """Schema estructurado para el LLM."""

    entries: list[FaqPair] = Field(default_factory=list)


class FaqExtractorError(RuntimeError):
    """Falla del extractor LLM (red, schema invalido, timeout)."""


class FaqExtractorProtocol(Protocol):
    """Protocolo para inyectar el extractor (tests pueden pasar mocks)."""

    async def extract(self, markdown: str) -> list[FaqPair]: ...


_SYSTEM_PROMPT = """\
Sos un asistente que extrae pares pregunta-respuesta de un balotario
veterinario en formato libre. El balotario suele tener preguntas tipo
"• ¿...?" seguidas de una respuesta multilinea.

Reglas:
- Solo devolves pares completos (pregunta + respuesta).
- No inventes informacion, no parafrasees, no resumas: copia el texto
  exactamente como aparece.
- Si un bloque no tiene respuesta clara, descartalo.
- Devolves JSON valido siguiendo el schema dado, sin texto extra.
"""

_USER_PROMPT_TEMPLATE = """\
Aca esta el balotario completo. Extrae todas las entradas Q/A.

<balotario>
{markdown}
</balotario>
"""


@dataclass(slots=True)
class FaqExtractor:
    """Implementacion default: usa un `BaseChatModel` con structured output."""

    chat_model: BaseChatModel

    async def extract(self, markdown: str) -> list[FaqPair]:
        if not markdown or not markdown.strip():
            return []

        structured = self.chat_model.with_structured_output(FaqList)
        try:
            result = await structured.ainvoke(
                [
                    SystemMessage(content=_SYSTEM_PROMPT),
                    HumanMessage(
                        content=_USER_PROMPT_TEMPLATE.format(markdown=markdown)
                    ),
                ]
            )
        except Exception as exc:  # pragma: no cover - se cubre via mock
            _logger.warning(
                "faq_extractor_failed",
                action="extract",
                error=str(exc)[:200],
            )
            raise FaqExtractorError(str(exc)) from exc

        if isinstance(result, dict):
            try:
                result = FaqList(**result)
            except Exception as exc:
                raise FaqExtractorError(
                    f"schema_invalid: {exc}"
                ) from exc

        if not isinstance(result, FaqList):
            try:
                result = FaqList.model_validate_json(json.dumps(result))
            except Exception as exc:  # pragma: no cover - defensive
                raise FaqExtractorError(
                    f"unexpected_extractor_output: {type(result).__name__}"
                ) from exc

        return [
            entry
            for entry in result.entries
            if entry.question.strip() and entry.answer.strip()
        ]
