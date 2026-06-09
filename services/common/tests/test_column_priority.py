"""Tests de prioridad de columnas del comparador (spec 016)."""

from biomont_common.comparison.column_priority import default_display_tier
from biomont_common.comparison.presenter import build_redactor_input
from biomont_common.schemas.comparison import (
    ComparisonDiffItem,
    ComparisonDiffResult,
    ComparisonSimilarityItem,
)
from uuid import uuid4


def test_default_display_tier_proteggo_headers() -> None:
    assert default_display_tier("tiempo_de_efecto_meses", "Tiempo de efecto (meses)") == 1
    assert default_display_tier("f_farmaceutica", "FORMA FARMACÉUTICA (presentacion)") == 1
    assert default_display_tier("via_de_adm", "VIA DE ADMINISTRACION") == 1
    assert default_display_tier("especies", "ESPECIES") == 1
    assert default_display_tier("indicaciones", "Indicaciones") == 2
    assert default_display_tier("precauciones", "PRECAUCIONES") == 4


def test_build_redactor_input_respects_display_tier_from_db() -> None:
    diff = ComparisonDiffResult(
        subject_product_id=uuid4(),
        subject_name="Proteggo M",
        competitor_name="Protego 3M",
        published_version=2,
        differences=[
            ComparisonDiffItem(
                column_key="precauciones",
                header_label="PRECAUCIONES",
                subject_value="A",
                competitor_value="B",
                sort_order=99,
                display_tier=4,
            ),
            ComparisonDiffItem(
                column_key="tiempo_de_efecto_meses",
                header_label="TIEMPO DE EFECTO",
                subject_value="3",
                competitor_value="12",
                sort_order=1,
                display_tier=1,
            ),
            ComparisonDiffItem(
                column_key="indicaciones",
                header_label="INDICACIONES",
                subject_value="X",
                competitor_value="Y",
                sort_order=2,
                display_tier=1,
            ),
        ],
        similarities=[
            ComparisonSimilarityItem(
                column_key="via_de_adm",
                header_label="VIA DE ADM",
                shared_value="Oral",
                sort_order=3,
                display_tier=1,
            ),
        ],
    )
    inp = build_redactor_input(diff, "comparar proteggo")
    assert inp.items[0].column_key == "tiempo_de_efecto_meses"
    assert all(i.column_key != "precauciones" for i in inp.items)
    assert inp.similarity_items[0].column_key == "via_de_adm"
