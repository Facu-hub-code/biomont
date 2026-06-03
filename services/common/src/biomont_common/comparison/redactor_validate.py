"""Guardrails del redactor de comparacion (spec 013)."""

from __future__ import annotations

import re
import unicodedata

from biomont_common.schemas.comparison import (
    ComparisonRedactorInput,
    ComparisonRedactorOutput,
)

_BLOCKED_WORDS: frozenset[str] = frozenset(
    {
        "mejor",
        "peor",
        "recomiendo",
        "recomendamos",
        "superior",
        "inferior",
        "ganador",
        "preferible",
        "mas eficaz",
        "más eficaz",
        "menos eficaz",
    }
)

_NUMERIC_TOKEN = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:%|mg/kg|mg|ml/kg|ml|kg|g)?",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return normalized.encode("ascii", "ignore").decode("ascii")


def _extract_numeric_tokens(text: str) -> set[str]:
    found: set[str] = set()
    for match in _NUMERIC_TOKEN.finditer(text):
        token = re.sub(r"\s+", "", match.group(0).lower())
        found.add(token)
        num = re.match(r"(\d+(?:[.,]\d+)?)", token)
        if num:
            found.add(num.group(1).replace(",", "."))
    return found


def validate_redactor_output(
    output: ComparisonRedactorOutput,
    redactor_input: ComparisonRedactorInput,
) -> tuple[bool, str | None]:
    """RF-9: True si la salida es aceptable."""

    allowed_keys = {i.column_key for i in redactor_input.items}
    items_by_key = {i.column_key: i for i in redactor_input.items}

    combined_text = " ".join(
        [
            output.opening,
            output.footer,
            output.closing_hint or "",
            *[b.text for b in output.bullets],
        ]
    )
    norm = _normalize(combined_text)
    for blocked in _BLOCKED_WORDS:
        if blocked in norm:
            return False, f"blocked_word:{blocked}"

    for bullet in output.bullets:
        if bullet.column_key not in allowed_keys:
            return False, f"unknown_column:{bullet.column_key}"
        item = items_by_key[bullet.column_key]
        allowed_nums = _extract_numeric_tokens(
            item.subject_snippet + " " + item.competitor_snippet
        )
        bullet_nums = _extract_numeric_tokens(bullet.text)
        novel = bullet_nums - allowed_nums
        if novel:
            return False, f"novel_numeric:{','.join(sorted(novel)[:3])}"

    if redactor_input.presentation_mode == "summary" and not output.bullets:
        return False, "empty_bullets_summary"

    return True, None
