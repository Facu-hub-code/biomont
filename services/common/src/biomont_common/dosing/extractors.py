"""Extraccion determinista de peso, especie y edad (spec 011)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

_WEIGHT_KG_RE = re.compile(
    r"(?:de\s+)?(\d+(?:[.,]\d+)?)\s*(?:kg|kilos?|kilo)\b",
    re.IGNORECASE,
)
_WEIGHT_LB_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:lb|libras?)\b",
    re.IGNORECASE,
)

_SPECIES_MAP: list[tuple[str, str]] = [
    ("ternero", "calf"),
    ("ternera", "calf"),
    ("becerro", "calf"),
    ("becerra", "calf"),
    ("vaca", "bovine"),
    ("vacas", "bovine"),
    ("bovino", "bovine"),
    ("bovina", "bovine"),
    ("toro", "bovine"),
    ("novillo", "bovine"),
    ("gato", "feline"),
    ("gata", "feline"),
    ("felino", "feline"),
    ("felina", "feline"),
    ("perro", "canine"),
    ("perra", "canine"),
    ("canino", "canine"),
    ("canina", "canine"),
    ("cachorro", "canine"),
    ("cachorra", "canine"),
    ("equino", "equine"),
    ("caballo", "equine"),
    ("yegua", "equine"),
    ("potrillo", "equine"),
]

_AGE_WEEKS_RE = re.compile(
    r"(\d+)\s*(?:semanas?|sem)\b",
    re.IGNORECASE,
)
_AGE_MONTHS_RE = re.compile(
    r"(\d+)\s*(?:meses?|mes)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class DosingContextExtract:
    weight_kg: Decimal | None = None
    species: str | None = None
    age_weeks: int | None = None
    needs_weight: bool = False
    needs_species: bool = False
    rejected_lb: bool = False


def _parse_decimal(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def extract_dosing_context(query: str) -> DosingContextExtract:
    """Extrae peso, especie y edad del mensaje del usuario."""

    q = query.casefold()

    if _WEIGHT_LB_RE.search(q):
        return DosingContextExtract(rejected_lb=True, needs_weight=True)

    weight: Decimal | None = None
    for match in _WEIGHT_KG_RE.finditer(q):
        parsed = _parse_decimal(match.group(1))
        if parsed is not None:
            weight = parsed

    species: str | None = None
    for token, slug in _SPECIES_MAP:
        if re.search(rf"\b{re.escape(token)}\b", q):
            species = slug
            break

    age_weeks: int | None = None
    month_match = _AGE_MONTHS_RE.search(q)
    week_match = _AGE_WEEKS_RE.search(q)
    if month_match:
        age_weeks = int(month_match.group(1)) * 4
    elif week_match:
        age_weeks = int(week_match.group(1))

    needs_weight = weight is None
    needs_species = species is None

    return DosingContextExtract(
        weight_kg=weight,
        species=species,
        age_weeks=age_weeks,
        needs_weight=needs_weight,
        needs_species=needs_species,
    )
