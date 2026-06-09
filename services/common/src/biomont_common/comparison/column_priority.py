"""Prioridad de columnas del comparador (spec 016)."""

from __future__ import annotations

import unicodedata

# tier 1 = destacada en summary, 4 = detalle largo
_DEFAULT_TIER_BY_KEY: dict[str, int] = {
    "formula": 1,
    "dosis": 1,
    "especies_de_destino": 1,
    "especies": 1,
    "f_farmaceutica": 1,
    "via_de_adm": 1,
    "tiempo_de_efecto_meses": 1,
    "tiempo_de_efecto": 1,
    "indicaciones": 2,
    "producto": 3,
    "laboratorio_fabricante": 3,
    "pais": 3,
    "empresa_importadora": 3,
    "precauciones": 4,
    "contraindicaciones": 4,
    "reacciones_adversas": 4,
}

_HEADER_TIER_HINTS: tuple[tuple[str, int], ...] = (
    ("tiempo de efecto", 1),
    ("forma farmaceutica", 1),
    ("forma farmac", 1),
    ("via de adm", 1),
    ("vía de adm", 1),
    ("especies", 1),
    ("indicaciones", 2),
    ("precauciones", 4),
    ("contraindicaciones", 4),
)


def _normalize_label(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return normalized.encode("ascii", "ignore").decode("ascii")


def default_display_tier(column_key: str, header_label: str = "") -> int:
    """Heuristica inicial al importar Excel (overrideable desde BO)."""

    if column_key in _DEFAULT_TIER_BY_KEY:
        return _DEFAULT_TIER_BY_KEY[column_key]
    label = _normalize_label(header_label)
    for phrase, tier in _HEADER_TIER_HINTS:
        if phrase in label:
            return tier
    return 3


def tier_for_column_key(column_key: str) -> int:
    """Fallback cuando no hay tier persistido en DB."""

    return _DEFAULT_TIER_BY_KEY.get(column_key, 3)
