"""Tests del presenter del comparador (spec 013)."""

from uuid import uuid4

from biomont_common.comparison.presenter import (
    build_redactor_input,
    detect_presentation_mode,
    format_comparison_diff_brief,
    format_focus_no_difference,
)
from biomont_common.comparison.redactor_validate import validate_redactor_output
from biomont_common.schemas.comparison import (
    ComparisonDiffItem,
    ComparisonDiffResult,
    ComparisonRedactorBullet,
    ComparisonRedactorInput,
    ComparisonRedactorItem,
    ComparisonRedactorOutput,
)


def _diff(*items: tuple[str, str, str, str]) -> ComparisonDiffResult:
    differences = [
        ComparisonDiffItem(
            column_key=key,
            header_label=label,
            subject_value=subj,
            competitor_value=comp,
            sort_order=i,
        )
        for i, (key, label, subj, comp) in enumerate(items)
    ]
    return ComparisonDiffResult(
        subject_product_id=uuid4(),
        subject_name="MARVO 20",
        competitor_name="MARBOXI",
        published_version=1,
        differences=differences,
    )


def test_detect_presentation_mode_summary() -> None:
    mode, focus = detect_presentation_mode("MARVO 20 versus Marboxi diferencias")
    assert mode == "summary"
    assert focus is None


def test_detect_presentation_mode_focus_dosis() -> None:
    mode, focus = detect_presentation_mode("MARVO 20 vs Marboxi solo en dosis")
    assert mode == "focus"
    assert focus == "dosis"


def test_detect_presentation_mode_full() -> None:
    mode, _ = detect_presentation_mode("listame todas las diferencias")
    assert mode == "full"


def test_build_redactor_input_summary_limits_highlights() -> None:
    diff = _diff(
        ("formula", "FÓRMULA", "A", "B"),
        ("dosis", "DOSIS", "C", "D"),
        ("pais", "PAIS", "PE", "PE2"),
        ("precauciones", "PRECAUCIONES", "x" * 400, "y" * 400),
    )
    inp = build_redactor_input(diff, "comparar")
    assert inp.presentation_mode == "summary"
    assert len(inp.highlight_items) <= 5
    assert inp.other_items_count >= 1
    assert all(i.tier <= 2 for i in inp.items)


def test_build_redactor_input_focus_filters_column() -> None:
    diff = _diff(
        ("formula", "FÓRMULA", "A", "B"),
        ("dosis", "DOSIS", "C", "D"),
    )
    inp = build_redactor_input(diff, "solo dosis")
    assert inp.presentation_mode == "focus"
    assert len(inp.items) == 1
    assert inp.items[0].column_key == "dosis"


def test_format_focus_no_difference() -> None:
    text = format_focus_no_difference(
        subject_name="MARVO 20",
        competitor_name="MARBOXI",
        column_key="pais",
        header_label="PAIS",
    )
    assert "coincide" in text.lower()


def test_validate_rejects_blocked_word() -> None:
    inp = ComparisonRedactorInput(
        subject_name="A",
        competitor_name="B",
        published_version=1,
        presentation_mode="summary",
        highlight_items=[
            ComparisonRedactorItem(
                column_key="dosis",
                header_label="DOSIS",
                tier=1,
                subject_snippet="1 ml/10 kg",
                competitor_snippet="2 ml/10 kg",
            )
        ],
        items=[
            ComparisonRedactorItem(
                column_key="dosis",
                header_label="DOSIS",
                tier=1,
                subject_snippet="1 ml/10 kg",
                competitor_snippet="2 ml/10 kg",
            )
        ],
        other_items_count=0,
    )
    out = ComparisonRedactorOutput(
        opening="Comparacion",
        bullets=[
            ComparisonRedactorBullet(
                column_key="dosis",
                text="Es mejor el producto A con 1 ml/10 kg",
            )
        ],
        footer="Fuente: comparativa comercial Biomont (v1).",
    )
    ok, reason = validate_redactor_output(out, inp)
    assert not ok
    assert reason and "blocked" in reason


def test_validate_rejects_novel_numeric() -> None:
    inp = ComparisonRedactorInput(
        subject_name="A",
        competitor_name="B",
        published_version=1,
        presentation_mode="summary",
        highlight_items=[],
        items=[
            ComparisonRedactorItem(
                column_key="dosis",
                header_label="DOSIS",
                tier=1,
                subject_snippet="1 tableta/10 kg",
                competitor_snippet="2 tabletas/10 kg",
            )
        ],
        other_items_count=0,
    )
    out = ComparisonRedactorOutput(
        opening="Comparacion",
        bullets=[
            ComparisonRedactorBullet(
                column_key="dosis",
                text="Dosis de 99 mg/kg en A",
            )
        ],
        footer="Fuente: comparativa comercial Biomont (v1).",
    )
    ok, reason = validate_redactor_output(out, inp)
    assert not ok
    assert reason and "novel_numeric" in reason


def test_brief_includes_other_count_hint() -> None:
    diff = _diff(
        ("formula", "FÓRMULA", "A", "B"),
        ("precauciones", "PRECAUCIONES", "long", "longer"),
    )
    inp = build_redactor_input(diff, "comparar")
    text = format_comparison_diff_brief(inp)
    assert "diferencias más" in text
