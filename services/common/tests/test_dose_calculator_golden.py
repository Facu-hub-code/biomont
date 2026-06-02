"""Golden parametrizado del motor de dosis (>=30 casos)."""

from decimal import Decimal
from uuid import uuid4

import pytest

from biomont_common.dosing.calculator import calculate_dose
from biomont_common.schemas.dosing import (
    CompletenessStatus,
    DoseCalculationError,
    DosingOutputUnit,
    DosingProfile,
    DosingRule,
    DosingRuleType,
)


def _bands() -> list[DosingRule]:
    specs = [
        ("2", "4.5", "50"),
        ("4.5", "10", "100"),
        ("10", "20", "250"),
        ("20", "40", "1000"),
        ("40", "60", "3000"),
    ]
    return [
        DosingRule(
            id=uuid4(),
            profile_id=uuid4(),
            rule_type=DosingRuleType.weight_band,
            weight_min_kg=Decimal(lo),
            weight_max_kg=Decimal(hi),
            output_value=Decimal(out),
            output_unit=DosingOutputUnit.mg,
            published_version=1,
        )
        for lo, hi, out in specs
    ]


PROFILE = DosingProfile(
    id=uuid4(),
    product_id=uuid4(),
    species="canine",
    supports_dose_calculation=True,
    completeness_status=CompletenessStatus.complete,
    published_version=1,
)

WEIGHT_EXPECTED = [
    ("3", "50"),
    ("5", "100"),
    ("15", "250"),
    ("25", "1000"),
    ("45", "3000"),
    ("4.5", "50"),
    ("10", "100"),
    ("20", "250"),
    ("40", "1000"),
]


@pytest.mark.parametrize("weight,expected_mg", WEIGHT_EXPECTED)
def test_golden_weight_bands(weight: str, expected_mg: str) -> None:
    result = calculate_dose(
        profile=PROFILE,
        rules=_bands(),
        product_id=PROFILE.product_id,
        product_name="Proteggo 3M",
        weight_kg=Decimal(weight),
        species="canine",
    )
    assert not isinstance(result, DoseCalculationError)
    assert result.output_value == Decimal(expected_mg).quantize(Decimal("0.01"))


FORMULA_CASES = [
    ("10", "10.00"),
    ("25", "25.00"),
    ("100", "100.00"),
    ("450", "450.00"),
    ("1.5", "1.50"),
]


@pytest.mark.parametrize("weight,expected_ml", FORMULA_CASES)
def test_golden_formula_ml_per_kg(weight: str, expected_ml: str) -> None:
    profile = DosingProfile(
        id=uuid4(),
        product_id=uuid4(),
        species="bovine",
        supports_dose_calculation=True,
        completeness_status=CompletenessStatus.complete,
        published_version=1,
    )
    rules = [
        DosingRule(
            id=uuid4(),
            profile_id=profile.id,
            rule_type=DosingRuleType.formula,
            formula_numerator=Decimal("1"),
            formula_denominator=Decimal("1"),
            formula_per_kg=True,
            output_unit=DosingOutputUnit.ml,
            published_version=1,
        )
    ]
    result = calculate_dose(
        profile=profile,
        rules=rules,
        product_id=profile.product_id,
        product_name="Tulaviot",
        weight_kg=Decimal(weight),
        species="bovine",
    )
    assert not isinstance(result, DoseCalculationError)
    assert result.output_value == Decimal(expected_ml)


TABLET_FORMULA = [
    ("10", "1.00"),
    ("20", "2.00"),
    ("30", "3.00"),
]


@pytest.mark.parametrize("weight,tablets", TABLET_FORMULA)
def test_golden_one_tablet_per_10kg(weight: str, tablets: str) -> None:
    profile = DosingProfile(
        id=uuid4(),
        product_id=uuid4(),
        species="canine",
        supports_dose_calculation=True,
        completeness_status=CompletenessStatus.complete,
        published_version=1,
    )
    rules = [
        DosingRule(
            id=uuid4(),
            profile_id=profile.id,
            rule_type=DosingRuleType.formula,
            formula_numerator=Decimal("1"),
            formula_denominator=Decimal("10"),
            formula_per_kg=True,
            output_unit=DosingOutputUnit.tablets,
            published_version=1,
            label="1 comp/10 kg",
        )
    ]
    result = calculate_dose(
        profile=profile,
        rules=rules,
        product_id=profile.product_id,
        product_name="MARVO 20",
        weight_kg=Decimal(weight),
        species="canine",
    )
    assert not isinstance(result, DoseCalculationError)
    assert result.output_value == Decimal(tablets)


OUT_OF_RANGE = ["0.5", "70", "1000"]


@pytest.mark.parametrize("weight", OUT_OF_RANGE)
def test_golden_out_of_band_abstains(weight: str) -> None:
    result = calculate_dose(
        profile=PROFILE,
        rules=_bands(),
        product_id=PROFILE.product_id,
        product_name="Proteggo 3M",
        weight_kg=Decimal(weight),
        species="canine",
    )
    assert isinstance(result, DoseCalculationError)
