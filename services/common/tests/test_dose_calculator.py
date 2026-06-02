"""Tests del motor de dosis determinista."""

from decimal import Decimal
from uuid import uuid4

from biomont_common.dosing.calculator import calculate_dose, format_dose_response
from biomont_common.dosing.extractors import extract_dosing_context
from biomont_common.schemas.dosing import (
    CompletenessStatus,
    DoseCalculationError,
    DosingOutputUnit,
    DosingProfile,
    DosingRule,
    DosingRuleType,
)


def _profile(**kwargs) -> DosingProfile:
    defaults = dict(
        id=uuid4(),
        product_id=uuid4(),
        species="canine",
        supports_dose_calculation=True,
        completeness_status=CompletenessStatus.complete,
        published_version=1,
    )
    defaults.update(kwargs)
    return DosingProfile(**defaults)


def _band_rule(
    wmin: str,
    wmax: str,
    out: str,
    unit: DosingOutputUnit = DosingOutputUnit.mg,
    label: str | None = None,
) -> DosingRule:
    return DosingRule(
        id=uuid4(),
        profile_id=uuid4(),
        rule_type=DosingRuleType.weight_band,
        label=label,
        weight_min_kg=Decimal(wmin),
        weight_max_kg=Decimal(wmax),
        output_value=Decimal(out),
        output_unit=unit,
        published_version=1,
    )


def test_weight_band_lookup_center() -> None:
    profile = _profile()
    rules = [_band_rule("20", "40", "1000", label="PROTEGGO 3M 1000 mg")]
    result = calculate_dose(
        profile=profile,
        rules=rules,
        product_id=profile.product_id,
        product_name="Proteggo 3M",
        weight_kg=Decimal("25"),
        species="canine",
    )
    assert not isinstance(result, DoseCalculationError)
    assert result.output_value == Decimal("1000.00")
    assert "1000 mg" in format_dose_response(result)


def test_weight_band_border_inclusive() -> None:
    profile = _profile()
    rules = [
        DosingRule(
            id=uuid4(),
            profile_id=uuid4(),
            rule_type=DosingRuleType.weight_band,
            weight_min_kg=Decimal("4.5"),
            weight_max_kg=Decimal("10"),
            weight_min_inclusive=False,
            weight_max_inclusive=True,
            output_value=Decimal("250"),
            output_unit=DosingOutputUnit.mg,
            published_version=1,
        ),
        _band_rule("10", "20", "500"),
    ]
    result = calculate_dose(
        profile=profile,
        rules=rules,
        product_id=profile.product_id,
        product_name="Proteggo M",
        weight_kg=Decimal("5"),
        species="canine",
    )
    assert not isinstance(result, DoseCalculationError)
    assert result.output_value == Decimal("250.00")


def test_formula_ml_per_kg() -> None:
    profile = _profile(species="bovine")
    rules = [
        DosingRule(
            id=uuid4(),
            profile_id=uuid4(),
            rule_type=DosingRuleType.formula,
            formula_numerator=Decimal("1"),
            formula_denominator=Decimal("1"),
            formula_per_kg=True,
            output_unit=DosingOutputUnit.ml,
            published_version=1,
            label="1 ml/kg",
        )
    ]
    result = calculate_dose(
        profile=profile,
        rules=rules,
        product_id=profile.product_id,
        product_name="Tulaviot",
        weight_kg=Decimal("450"),
        species="bovine",
    )
    assert result.output_value == Decimal("450.00")
    assert result.output_unit == DosingOutputUnit.ml


def test_incomplete_catalog_blocks() -> None:
    profile = _profile(completeness_status=CompletenessStatus.incomplete)
    result = calculate_dose(
        profile=profile,
        rules=[],
        product_id=profile.product_id,
        product_name="X",
        weight_kg=Decimal("10"),
        species="canine",
    )
    assert isinstance(result, DoseCalculationError)
    assert result.code == "incomplete_catalog"


def test_extract_weight_and_species() -> None:
    ctx = extract_dosing_context("perro de 25 kg que tableta de marvo")
    assert ctx.weight_kg == Decimal("25")
    assert ctx.species == "canine"
    assert not ctx.needs_weight


def test_extract_calf_species() -> None:
    ctx = extract_dosing_context("ternero de 80 kg augmentha")
    assert ctx.species == "calf"
    assert ctx.weight_kg == Decimal("80")


def test_extract_needs_weight() -> None:
    ctx = extract_dosing_context("que tableta de proteggo m")
    assert ctx.needs_weight


def test_extract_rejects_lb() -> None:
    ctx = extract_dosing_context("perro de 50 lb")
    assert ctx.rejected_lb
