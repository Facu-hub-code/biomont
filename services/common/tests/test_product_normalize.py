"""Tests del helper `normalize_text` (spec 003).

Debe mantenerse semanticamente alineado con `public.immutable_unaccent_lower`
del SQL: unaccent + lower + colapso de espacios.
"""

from __future__ import annotations

import pytest

from biomont_common.db.product_repository import (
    normalize_text,
    significant_alias_tokens,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Proteggo 3M", "proteggo 3m"),
        ("  Próteggo   3M  ", "proteggo 3m"),
        ("ÁÉÍÓÚÑ", "aeioun"),
        ("ñoño", "nono"),
        ("", ""),
        ("el de 3 meses", "el de 3 meses"),
    ],
)
def test_normalize_text_cases(raw: str, expected: str) -> None:
    assert normalize_text(raw) == expected


def test_significant_alias_tokens_extracts_product_mentions() -> None:
    q = normalize_text("Cuales son los efectos adversos del protego")
    tokens = significant_alias_tokens(q)
    assert "protego" in tokens
    assert "efectos" in tokens


def test_significant_alias_tokens_drops_short_and_stopwords() -> None:
    tokens = significant_alias_tokens(
        normalize_text("Cual es el protocolo")
    )
    assert "protocolo" in tokens
    assert "cual" not in tokens
    assert "el" not in tokens
