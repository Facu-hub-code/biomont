"""Tests del presenter del comparador (spec 013 + 014)."""

from uuid import uuid4

from biomont_common.comparison.column_priority import default_display_tier
from biomont_common.comparison.presenter import (
    build_redactor_input,
    detect_presentation_mode,
    format_comparison_diff_brief,
    format_comparison_narrative_brief,
    format_focus_no_difference,
    normalize_summary_output,
)
from biomont_common.comparison.redactor_validate import validate_redactor_output
from biomont_common.schemas.comparison import (
    ComparisonDiffItem,
    ComparisonDiffResult,
    ComparisonRedactorBullet,
    ComparisonRedactorInput,
    ComparisonRedactorItem,
    ComparisonRedactorOutput,
    ComparisonSimilarityItem,
)

def _diff(
    *items: tuple[str, str, str, str],
    similarities: list[tuple[str, str, str]] | None = None,
) -> ComparisonDiffResult:
    differences = [
        ComparisonDiffItem(
            column_key=key,
            header_label=label,
            subject_value=subj,
            competitor_value=comp,
            sort_order=i,
            display_tier=default_display_tier(key, label),
        )
        for i, (key, label, subj, comp) in enumerate(items)
    ]
    sims = [
        ComparisonSimilarityItem(
            column_key=key,
            header_label=label,
            shared_value=val,
            sort_order=i,
            display_tier=default_display_tier(key, label),
        )
        for i, (key, label, val) in enumerate(similarities or [])
    ]
    return ComparisonDiffResult(
        subject_product_id=uuid4(),
        subject_name="MARVO 20",
        competitor_name="MARBOXI",
        published_version=1,
        differences=differences,
        similarities=sims,
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


def test_build_redactor_input_summary_includes_similarities() -> None:
    diff = _diff(
        ("formula", "FÓRMULA", "A", "B"),
        ("dosis", "DOSIS", "C", "D"),
        ("pais", "PAIS", "PE", "PE2"),
        ("precauciones", "PRECAUCIONES", "x" * 400, "y" * 400),
        similarities=[
            ("via_de_adm", "VÍA DE ADM", "Oral"),
            ("especies_de_destino", "ESPECIES", "Perros"),
        ],
    )
    inp = build_redactor_input(diff, "comparar")
    assert inp.presentation_mode == "summary"
    assert len(inp.similarity_items) <= 3
    assert len(inp.items) <= 3
    assert all(i.tier <= 2 for i in inp.items)
    assert inp.other_items_count >= 1


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


def test_validate_summary_rejects_blocked_word() -> None:
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
                subject_snippet="1 ml/10 kg",
                competitor_snippet="2 ml/10 kg",
            )
        ],
        similarity_items=[],
        other_items_count=0,
    )
    out = ComparisonRedactorOutput(
        paragraphs=["Es mejor el producto A con 1 ml/10 kg"],
        footer="Fuente: comparativa comercial Biomont (v1).",
    )
    ok, reason = validate_redactor_output(out, inp)
    assert not ok
    assert reason and "blocked" in reason


def test_validate_focus_rejects_novel_numeric() -> None:
    inp = ComparisonRedactorInput(
        subject_name="A",
        competitor_name="B",
        published_version=1,
        presentation_mode="focus",
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


def test_narrative_brief_covers_similarities_and_differences() -> None:
    diff = _diff(
        ("formula", "FÓRMULA", "A", "B"),
        ("precauciones", "PRECAUCIONES", "long", "longer"),
        similarities=[("via_de_adm", "VÍA DE ADM", "Oral")],
    )
    inp = build_redactor_input(diff, "comparar")
    text = format_comparison_narrative_brief(inp)
    assert "Comparación entre" in text
    assert "compartido" in text.lower()
    assert "FÓRMULA" in text
    assert "MARVO 20" in text
    assert "MARBOXI" in text
    assert "diferencias más" in text.lower() or "más detalle" in text.lower()


def test_narrative_brief_similarities_only() -> None:
    diff = _diff(
        similarities=[("via_de_adm", "VÍA DE ADM", "Oral")],
    )
    inp = build_redactor_input(diff, "comparar")
    text = format_comparison_narrative_brief(inp)
    assert "compartido" in text.lower()
    assert "No se registran diferencias" in text


def test_normalize_summary_converts_bullets_to_paragraphs() -> None:
    out = ComparisonRedactorOutput(
        opening="Comparacion entre A y B.",
        bullets=[
            ComparisonRedactorBullet(column_key="dosis", text="Dosis distintas."),
        ],
        footer="Fuente: comparativa comercial Biomont (v1).",
    )
    normalized = normalize_summary_output(out, "summary")
    assert len(normalized.paragraphs) == 2
    assert not normalized.bullets


def test_narrative_uses_clean_product_labels() -> None:
    diff = ComparisonDiffResult(
        subject_product_id=uuid4(),
        subject_name="Protego 3M",
        competitor_name="Bravecto",
        published_version=2,
        differences=[
            ComparisonDiffItem(
                column_key="indicaciones",
                header_label="INDICACIONES",
                subject_value="Control pulgas Biomont",
                competitor_value="Control pulgas competidor",
                sort_order=1,
            )
        ],
        similarities=[
            ComparisonSimilarityItem(
                column_key="dosis",
                header_label="DOSIS",
                shared_value="25 mg/kg",
                sort_order=0,
            )
        ],
    )
    inp = build_redactor_input(diff, "comparar")
    text = format_comparison_narrative_brief(inp)
    assert "112.5 mg" not in text
    assert "*Protego 3M*" in text
    assert "*Bravecto*" in text
