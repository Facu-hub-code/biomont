"""Guardrails del redactor de comparacion (spec 013 + 014)."""

from __future__ import annotations

import re
import unicodedata

from biomont_common.comparison.presenter import SUMMARY_BODY_MAX_LEN
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


def _allowed_numeric_tokens(redactor_input: ComparisonRedactorInput) -> set[str]:
    allowed: set[str] = set()
    for item in list(redactor_input.items) + list(redactor_input.similarity_items):
        allowed |= _extract_numeric_tokens(
            item.subject_snippet + " " + item.competitor_snippet
        )
    return allowed


def _validate_blocked_words(combined_text: str) -> tuple[bool, str | None]:
    norm = _normalize(combined_text)
    for blocked in _BLOCKED_WORDS:
        if blocked in norm:
            return False, f"blocked_word:{blocked}"
    return True, None


def _validate_novel_numerics(
    text: str, allowed_nums: set[str]
) -> tuple[bool, str | None]:
    novel = _extract_numeric_tokens(text) - allowed_nums
    if novel:
        return False, f"novel_numeric:{','.join(sorted(novel)[:3])}"
    return True, None


def validate_redactor_output(
    output: ComparisonRedactorOutput,
    redactor_input: ComparisonRedactorInput,
) -> tuple[bool, str | None]:
    """RF-9: True si la salida es aceptable."""

    allowed_nums = _allowed_numeric_tokens(redactor_input)

    if redactor_input.presentation_mode == "summary":
        body_parts = [p for p in output.paragraphs if p.strip()]
        hint = output.follow_up_hint or output.closing_hint or ""
        combined_text = " ".join(body_parts + [hint, output.footer])
        ok, reason = _validate_blocked_words(combined_text)
        if not ok:
            return ok, reason
        if not body_parts:
            return False, "empty_paragraphs_summary"
        if len(body_parts) > 2:
            return False, "too_many_paragraphs"
        body_len = len(" ".join(body_parts) + hint)
        if body_len > SUMMARY_BODY_MAX_LEN:
            return False, "body_too_long"
        for paragraph in body_parts:
            ok, reason = _validate_novel_numerics(paragraph, allowed_nums)
            if not ok:
                return ok, reason
        return True, None

    allowed_keys = {i.column_key for i in redactor_input.items}
    items_by_key = {i.column_key: i for i in redactor_input.items}

    combined_text = " ".join(
        [
            output.opening,
            output.footer,
            output.follow_up_hint or "",
            output.closing_hint or "",
            *[b.text for b in output.bullets],
        ]
    )
    ok, reason = _validate_blocked_words(combined_text)
    if not ok:
        return ok, reason

    for bullet in output.bullets:
        if bullet.column_key not in allowed_keys:
            return False, f"unknown_column:{bullet.column_key}"
        item = items_by_key[bullet.column_key]
        allowed_item_nums = _extract_numeric_tokens(
            item.subject_snippet + " " + item.competitor_snippet
        )
        ok, reason = _validate_novel_numerics(bullet.text, allowed_item_nums)
        if not ok:
            return ok, reason

    if redactor_input.presentation_mode == "focus" and not output.bullets:
        return False, "empty_bullets_focus"

    return True, None
