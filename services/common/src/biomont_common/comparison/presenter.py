"""Pre-procesamiento y formateo del comparador comercial (spec 013)."""

from __future__ import annotations

import unicodedata
from typing import Literal

from biomont_common.schemas.comparison import (
    ComparisonDiffItem,
    ComparisonDiffResult,
    ComparisonRedactorInput,
    ComparisonRedactorItem,
    ComparisonRedactorOutput,
)

SNIPPET_MAX_LEN = 280
BRIEF_VALUE_MAX_LEN = 200
HIGHLIGHT_MAX = 5

# tier 1 = destacada, 4 = detalle largo
_COLUMN_TIER: dict[str, int] = {
    "formula": 1,
    "dosis": 1,
    "especies_de_destino": 1,
    "especies": 1,
    "f_farmaceutica": 1,
    "via_de_adm": 1,
    "indicaciones": 2,
    "producto": 3,
    "laboratorio_fabricante": 3,
    "pais": 3,
    "empresa_importadora": 3,
    "precauciones": 4,
    "contraindicaciones": 4,
    "reacciones_adversas": 4,
}

_FOCUS_SYNONYMS: tuple[tuple[str, str], ...] = (
    ("dosificacion", "dosis"),
    ("dosificación", "dosis"),
    ("dosis", "dosis"),
    ("formula", "formula"),
    ("fórmula", "formula"),
    ("formulacion", "formula"),
    ("formulación", "formula"),
    ("especie", "especies_de_destino"),
    ("especies", "especies_de_destino"),
    ("indicacion", "indicaciones"),
    ("indicación", "indicaciones"),
    ("indicaciones", "indicaciones"),
    ("precaucion", "precauciones"),
    ("precaución", "precauciones"),
    ("precauciones", "precauciones"),
    ("contraindicacion", "contraindicaciones"),
    ("contraindicación", "contraindicaciones"),
    ("contraindicaciones", "contraindicaciones"),
    ("reacciones adversas", "reacciones_adversas"),
    ("via de adm", "via_de_adm"),
    ("vía de adm", "via_de_adm"),
    ("forma farmaceutica", "f_farmaceutica"),
    ("laboratorio", "laboratorio_fabricante"),
    ("pais", "pais"),
    ("país", "pais"),
    ("producto", "producto"),
)

_FULL_MARKERS: tuple[str, ...] = (
    "todas las diferencias",
    "todos los campos",
    "listame todo",
    "listá todo",
    "lista todo",
    "detalle completo",
    "comparacion completa",
    "comparación completa",
    "modo completo",
)

PresentationMode = Literal["summary", "focus", "full"]


def tier_for_column_key(column_key: str) -> int:
    return _COLUMN_TIER.get(column_key, 3)


def _normalize_query(query: str) -> str:
    normalized = unicodedata.normalize("NFKD", query.casefold())
    return normalized.encode("ascii", "ignore").decode("ascii")


def detect_presentation_mode(query: str) -> tuple[PresentationMode, str | None]:
    """Resuelve modo y column_key de foco (spec 013 RF-3)."""

    nq = _normalize_query(query)
    for marker in _FULL_MARKERS:
        if marker in nq:
            return "full", None
    for phrase, column_key in sorted(
        _FOCUS_SYNONYMS, key=lambda x: len(x[0]), reverse=True
    ):
        if phrase in nq:
            return "focus", column_key
    return "summary", None


def _snippet(value: str, *, max_len: int = SNIPPET_MAX_LEN) -> tuple[str, bool]:
    text = (value or "").strip()
    if len(text) <= max_len:
        return text, False
    return text[: max_len - 1].rstrip() + "…", True


def _to_redactor_item(item: ComparisonDiffItem) -> ComparisonRedactorItem:
    subj, subj_trunc = _snippet(item.subject_value)
    comp, comp_trunc = _snippet(item.competitor_value)
    return ComparisonRedactorItem(
        column_key=item.column_key,
        header_label=item.header_label,
        tier=tier_for_column_key(item.column_key),
        subject_snippet=subj,
        competitor_snippet=comp,
        truncated=subj_trunc or comp_trunc,
    )


def build_redactor_input(
    diff: ComparisonDiffResult,
    query: str,
) -> ComparisonRedactorInput:
    mode, focus_key = detect_presentation_mode(query)
    items_sorted = sorted(
        diff.differences,
        key=lambda d: (tier_for_column_key(d.column_key), d.sort_order),
    )
    all_redactor = [_to_redactor_item(d) for d in items_sorted]

    if mode == "focus" and focus_key:
        focus_items = [r for r in all_redactor if r.column_key == focus_key]
        other = len(all_redactor) - len(focus_items)
        return ComparisonRedactorInput(
            subject_name=diff.subject_name,
            competitor_name=diff.competitor_name,
            published_version=diff.published_version,
            presentation_mode=mode,
            focus_column_key=focus_key,
            highlight_items=focus_items[:1],
            items=focus_items,
            other_items_count=other,
        )

    if mode == "full":
        return ComparisonRedactorInput(
            subject_name=diff.subject_name,
            competitor_name=diff.competitor_name,
            published_version=diff.published_version,
            presentation_mode=mode,
            focus_column_key=None,
            highlight_items=all_redactor[:HIGHLIGHT_MAX],
            items=all_redactor,
            other_items_count=0,
        )

    highlights = [r for r in all_redactor if r.tier <= 2][:HIGHLIGHT_MAX]
    highlight_keys = {h.column_key for h in highlights}
    other_count = len(all_redactor) - len(highlight_keys)
    return ComparisonRedactorInput(
        subject_name=diff.subject_name,
        competitor_name=diff.competitor_name,
        published_version=diff.published_version,
        presentation_mode="summary",
        focus_column_key=None,
        highlight_items=highlights,
        items=highlights,
        other_items_count=max(0, other_count),
    )


def focus_column_label(column_key: str) -> str:
    for _phrase, key in _FOCUS_SYNONYMS:
        if key == column_key:
            return _phrase
    return column_key.replace("_", " ")


def format_focus_no_difference(
    *,
    subject_name: str,
    competitor_name: str,
    column_key: str,
    header_label: str | None = None,
) -> str:
    label = header_label or focus_column_label(column_key)
    return (
        f"En el cuadro comparativo entre **{subject_name}** y **{competitor_name}**, "
        f"el campo **{label}** coincide o no tiene datos diferenciados."
    )


def format_comparison_diff_brief(
    redactor_input: ComparisonRedactorInput,
    *,
    value_max_len: int = BRIEF_VALUE_MAX_LEN,
) -> str:
    """Fallback determinista (spec 013 RF-10)."""

    lines = [
        f"Comparando **{redactor_input.subject_name}** con "
        f"**{redactor_input.competitor_name}** "
        f"(datos validados v{redactor_input.published_version}):",
        "",
    ]
    items = redactor_input.items or redactor_input.highlight_items
    if not items:
        lines.append(
            "No se encontraron diferencias en los campos comparables del cuadro comercial."
        )
    else:
        for item in items:
            subj = item.subject_snippet
            comp = item.competitor_snippet
            if len(subj) > value_max_len:
                subj = subj[: value_max_len - 1] + "…"
            if len(comp) > value_max_len:
                comp = comp[: value_max_len - 1] + "…"
            lines.append(f"- **{item.header_label}**:")
            lines.append(f"  - {redactor_input.subject_name}: {subj}")
            lines.append(f"  - {redactor_input.competitor_name}: {comp}")
    if redactor_input.other_items_count > 0:
        lines.append("")
        lines.append(
            f"Hay {redactor_input.other_items_count} diferencias más en el cuadro "
            f"(ej. precauciones). Preguntá por un tema: dosis, fórmula, precauciones…"
        )
    lines.append("")
    lines.append(
        f"Fuente: comparativa comercial Biomont (v{redactor_input.published_version})."
    )
    return "\n".join(lines)


def format_comparison_diff_full(diff: ComparisonDiffResult) -> str:
    """Listado completo determinista (modo full sin LLM)."""

    from biomont_common.db.comparison_repository import format_comparison_diff

    return format_comparison_diff(diff)


def render_redactor_output(output: ComparisonRedactorOutput) -> str:
    lines = [output.opening.strip(), ""]
    for bullet in output.bullets:
        lines.append(f"- {bullet.text.strip()}")
    if output.closing_hint:
        lines.append("")
        lines.append(output.closing_hint.strip())
    lines.append("")
    lines.append(output.footer.strip())
    return "\n".join(lines)


def redactor_user_payload(redactor_input: ComparisonRedactorInput, query: str) -> str:
    """JSON legible para el prompt del LLM."""

    import json

    payload = {
        "user_query": query,
        "presentation_mode": redactor_input.presentation_mode,
        "subject_name": redactor_input.subject_name,
        "competitor_name": redactor_input.competitor_name,
        "published_version": redactor_input.published_version,
        "other_items_count": redactor_input.other_items_count,
        "items": [
            {
                "column_key": i.column_key,
                "header_label": i.header_label,
                "tier": i.tier,
                "subject_snippet": i.subject_snippet,
                "competitor_snippet": i.competitor_snippet,
            }
            for i in redactor_input.items
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
