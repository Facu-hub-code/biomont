"""Schemas del motor de dosis (spec 011)."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class DosingRuleType(str, Enum):
    formula = "formula"
    weight_band = "weight_band"


class DosingOutputUnit(str, Enum):
    ml = "ml"
    mg = "mg"
    tablets = "tablets"
    doses = "doses"


class CompletenessStatus(str, Enum):
    complete = "complete"
    incomplete = "incomplete"
    not_applicable = "not_applicable"


class DosingProfile(BaseModel):
    id: UUID
    product_id: UUID
    species: str
    supports_dose_calculation: bool = False
    min_age_weeks: int | None = None
    max_age_weeks: int | None = None
    min_weight_kg: Decimal | None = None
    max_weight_kg: Decimal | None = None
    completeness_status: CompletenessStatus = CompletenessStatus.incomplete
    published_version: int = 0


class DosingRule(BaseModel):
    id: UUID
    profile_id: UUID
    rule_type: DosingRuleType
    label: str | None = None
    formula_numerator: Decimal | None = None
    formula_denominator: Decimal | None = Field(default=Decimal("1"))
    formula_per_kg: bool = True
    weight_min_kg: Decimal | None = None
    weight_max_kg: Decimal | None = None
    weight_min_inclusive: bool = True
    weight_max_inclusive: bool = True
    output_value: Decimal | None = None
    output_unit: DosingOutputUnit = DosingOutputUnit.mg
    min_output: Decimal | None = None
    max_output: Decimal | None = None
    sort_order: int = 0
    is_active: bool = True
    published_version: int = 0


class DoseCalculationResult(BaseModel):
    product_id: UUID
    product_name: str
    species: str
    weight_kg: Decimal
    rule_type: DosingRuleType
    rule_label: str | None = None
    formula_description: str | None = None
    output_value: Decimal
    output_unit: DosingOutputUnit
    weight_band: str | None = None
    published_version: int
    profile_id: UUID


class DoseCalculationError(BaseModel):
    code: str
    message: str
