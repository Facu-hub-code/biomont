"""Tests del formateo de diff comparativo."""

from uuid import uuid4

from biomont_common.db.comparison_repository import format_comparison_diff
from biomont_common.schemas.comparison import ComparisonDiffItem, ComparisonDiffResult


def test_format_comparison_diff_lists_differences_neutrally() -> None:
    result = ComparisonDiffResult(
        subject_product_id=uuid4(),
        subject_name="OPRURIX",
        competitor_name="APOQUEL",
        published_version=1,
        differences=[
            ComparisonDiffItem(
                column_key="dosis",
                header_label="DOSIS",
                subject_value="0.4 a 0.6 mg/kg cada 12h",
                competitor_value="0.4 a 0.6 mg/kg cada 12 h",
            )
        ],
    )
    text = format_comparison_diff(result)
    assert "OPRURIX" in text
    assert "APOQUEL" in text
    assert "DOSIS" in text
    assert "mejor" not in text.lower()
    assert "peor" not in text.lower()


def test_slugify_column_from_admin_repo() -> None:
    from app.db.comparison_admin_repository import slugify_column

    assert slugify_column("FÓRMULA ") == "formula"
    assert slugify_column("ESPECIES DE DESTINO") == "especies_de_destino"
