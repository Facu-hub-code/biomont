"""Pre-procesamiento y formateo del comparador comercial (spec 013 + 014)."""

from __future__ import annotations

import unicodedata
from typing import Literal

from biomont_common.schemas.comparison import (
    ComparisonDiffItem,
    ComparisonDiffResult,
    ComparisonRedactorInput,
    ComparisonRedactorItem,
    ComparisonRedactorOutput,
    ComparisonSimilarityItem,
)
from biomont_common.whatsapp_format import normalize_whatsapp_markdown, wa_bold

SNIPPET_MAX_LEN = 280
BRIEF_VALUE_MAX_LEN = 200
HIGHLIGHT_MAX = 5
NARRATIVE_SUMMARY_MAX_SIM = 3
NARRATIVE_SUMMARY_MAX_DIFF = 3
SUMMARY_BODY_MAX_LEN = 900

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


def _to_similarity_redactor_item(item: ComparisonSimilarityItem) -> ComparisonRedactorItem:
    shared, truncated = _snippet(item.shared_value)
    return ComparisonRedactorItem(
        column_key=item.column_key,
        header_label=item.header_label,
        tier=tier_for_column_key(item.column_key),
        subject_snippet=shared,
        competitor_snippet=shared,
        truncated=truncated,
    )


def _sort_similarities(
    similarities: list[ComparisonSimilarityItem],
) -> list[ComparisonRedactorItem]:
    ordered = sorted(
        similarities,
        key=lambda s: (tier_for_column_key(s.column_key), s.sort_order),
    )
    return [_to_similarity_redactor_item(s) for s in ordered]


def _sort_differences(diff: ComparisonDiffResult) -> list[ComparisonRedactorItem]:
    items_sorted = sorted(
        diff.differences,
        key=lambda d: (tier_for_column_key(d.column_key), d.sort_order),
    )
    return [_to_redactor_item(d) for d in items_sorted]


def build_redactor_input(
    diff: ComparisonDiffResult,
    query: str,
) -> ComparisonRedactorInput:
    mode, focus_key = detect_presentation_mode(query)
    all_redactor = _sort_differences(diff)
    all_similarities = _sort_similarities(diff.similarities)

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
            similarity_items=[],
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
            similarity_items=all_similarities,
            other_items_count=0,
        )

    summary_sims = [s for s in all_similarities if s.tier <= 2][:NARRATIVE_SUMMARY_MAX_SIM]
    summary_diffs = [d for d in all_redactor if d.tier <= 2][:NARRATIVE_SUMMARY_MAX_DIFF]
    highlight_keys = {d.column_key for d in summary_diffs}
    other_count = len(all_redactor) - len(highlight_keys)
    return ComparisonRedactorInput(
        subject_name=diff.subject_name,
        competitor_name=diff.competitor_name,
        published_version=diff.published_version,
        presentation_mode="summary",
        focus_column_key=None,
        highlight_items=summary_diffs,
        items=summary_diffs,
        similarity_items=summary_sims,
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
        f"En el cuadro comparativo entre {wa_bold(subject_name)} y "
        f"{wa_bold(competitor_name)}, el campo {wa_bold(label)} coincide o no "
        f"tiene datos diferenciados."
    )


def _comparison_header(subject_name: str, competitor_name: str) -> str:
    return f"Comparación entre {wa_bold(subject_name)} y {wa_bold(competitor_name)}"


def _append_shared_field(lines: list[str], *, label: str, value: str) -> None:
    lines.extend([f"{wa_bold(label)} (compartido):", value, ""])


def _append_diff_field(
    lines: list[str],
    *,
    label: str,
    subject_name: str,
    competitor_name: str,
    subject_value: str,
    competitor_value: str,
) -> None:
    lines.extend(
        [
            f"{wa_bold(label)} {wa_bold(subject_name)}:",
            subject_value,
            f"{wa_bold(label)} {wa_bold(competitor_name)}:",
            competitor_value,
            "",
        ]
    )


def format_comparison_narrative_brief(
    redactor_input: ComparisonRedactorInput,
) -> str:
    """Fallback narrativo para modo summary (spec 014)."""

    subject_name = redactor_input.subject_name
    competitor_name = redactor_input.competitor_name
    sims = redactor_input.similarity_items
    diffs = redactor_input.items or redactor_input.highlight_items

    lines = [_comparison_header(subject_name, competitor_name), ""]

    if not sims and not diffs:
        lines.append(
            "No se encontraron campos comparables con datos en el cuadro comercial."
        )
        lines.append("")
    else:
        for item in sims:
            _append_shared_field(
                lines,
                label=item.header_label,
                value=item.subject_snippet,
            )
        for item in diffs:
            _append_diff_field(
                lines,
                label=item.header_label,
                subject_name=subject_name,
                competitor_name=competitor_name,
                subject_value=item.subject_snippet,
                competitor_value=item.competitor_snippet,
            )
        if sims and not diffs:
            lines.append(
                "No se registran diferencias en los ejes clínicos principales del cuadro."
            )
            lines.append("")

    if redactor_input.other_items_count > 0:
        lines.append(
            "Hay más detalle en el cuadro (precauciones, indicaciones, etc.). "
            "Preguntá por un tema concreto: dosis, fórmula, precauciones…"
        )
        lines.append("")
    lines.append(
        f"Fuente: comparativa comercial Biomont (v{redactor_input.published_version})."
    )
    return "\n".join(lines)


def format_comparison_diff_brief(
    redactor_input: ComparisonRedactorInput,
    *,
    value_max_len: int = BRIEF_VALUE_MAX_LEN,
) -> str:
    """Fallback determinista por columna (modo focus)."""

    lines = [
        _comparison_header(
            redactor_input.subject_name, redactor_input.competitor_name
        ),
        f"(datos validados v{redactor_input.published_version})",
        "",
    ]
    items = redactor_input.items or redactor_input.highlight_items
    if not items:
        lines.append(
            "No se encontraron diferencias en los campos comparables del cuadro comercial."
        )
        lines.append("")
    else:
        for item in items:
            subj = item.subject_snippet
            comp = item.competitor_snippet
            if len(subj) > value_max_len:
                subj = subj[: value_max_len - 1] + "…"
            if len(comp) > value_max_len:
                comp = comp[: value_max_len - 1] + "…"
            _append_diff_field(
                lines,
                label=item.header_label,
                subject_name=redactor_input.subject_name,
                competitor_name=redactor_input.competitor_name,
                subject_value=subj,
                competitor_value=comp,
            )
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


def normalize_summary_output(
    output: ComparisonRedactorOutput,
    presentation_mode: str,
) -> ComparisonRedactorOutput:
    """Convierte opening+bullets legacy a paragraphs en modo summary."""

    if presentation_mode != "summary":
        return output
    if any(p.strip() for p in output.paragraphs):
        return output

    paragraphs: list[str] = []
    if output.opening.strip():
        paragraphs.append(output.opening.strip())
    if output.bullets:
        bullet_text = " ".join(b.text.strip() for b in output.bullets[:3] if b.text.strip())
        if bullet_text:
            paragraphs.append(bullet_text)
    if not paragraphs:
        return output
    return output.model_copy(
        update={"paragraphs": paragraphs[:2], "opening": "", "bullets": []}
    )


def render_redactor_output(output: ComparisonRedactorOutput) -> str:
    if output.paragraphs:
        lines = [p.strip() for p in output.paragraphs if p.strip()]
        hint = output.follow_up_hint or output.closing_hint
        if hint:
            lines.append("")
            lines.append(hint.strip())
        lines.append("")
        lines.append(output.footer.strip())
        return normalize_whatsapp_markdown("\n".join(lines))

    lines = [output.opening.strip(), ""]
    for bullet in output.bullets:
        lines.append(f"- {bullet.text.strip()}")
    hint = output.follow_up_hint or output.closing_hint
    if hint:
        lines.append("")
        lines.append(hint.strip())
    lines.append("")
    lines.append(output.footer.strip())
    return normalize_whatsapp_markdown("\n".join(lines))


def redactor_user_payload(redactor_input: ComparisonRedactorInput, query: str) -> str:
    """JSON legible para el prompt del LLM."""

    import json

    def _item_dict(i: ComparisonRedactorItem) -> dict:
        return {
            "column_key": i.column_key,
            "header_label": i.header_label,
            "tier": i.tier,
            "subject_snippet": i.subject_snippet,
            "competitor_snippet": i.competitor_snippet,
        }

    payload = {
        "user_query": query,
        "presentation_mode": redactor_input.presentation_mode,
        "subject_name": redactor_input.subject_name,
        "competitor_name": redactor_input.competitor_name,
        "published_version": redactor_input.published_version,
        "other_items_count": redactor_input.other_items_count,
        "similarity_items": [_item_dict(i) for i in redactor_input.similarity_items],
        "difference_items": [_item_dict(i) for i in redactor_input.items],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
