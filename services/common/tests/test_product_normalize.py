"""Tests del helper `normalize_text` (spec 003).

Debe mantenerse semanticamente alineado con `public.immutable_unaccent_lower`
del SQL: unaccent + lower + colapso de espacios.
"""

from __future__ import annotations

import pytest

from biomont_common.db.product_repository import normalize_text


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
