"""Schemas API de dosis."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class DosingProfileOut(BaseModel):
    id: UUID
    product_id: UUID
    species: str
    supports_dose_calculation: bool
    min_age_weeks: int | None = None
    max_age_weeks: int | None = None
    min_weight_kg: Decimal | None = None
    max_weight_kg: Decimal | None = None
    completeness_status: str
    completeness_notes: str | None = None
    published_version: int


class DosingProfileUpsert(BaseModel):
    species: str
    supports_dose_calculation: bool = False
    min_age_weeks: int | None = None
    max_age_weeks: int | None = None
    min_weight_kg: Decimal | None = None
    max_weight_kg: Decimal | None = None


class DosingRuleOut(BaseModel):
    id: UUID
    profile_id: UUID
    rule_type: str
    label: str | None = None
    formula_numerator: Decimal | None = None
    formula_denominator: Decimal | None = None
    formula_per_kg: bool = True
    weight_min_kg: Decimal | None = None
    weight_max_kg: Decimal | None = None
    weight_min_inclusive: bool = True
    weight_max_inclusive: bool = True
    output_value: Decimal | None = None
    output_unit: str = "mg"
    min_output: Decimal | None = None
    max_output: Decimal | None = None
    sort_order: int = 0
    is_active: bool = True
    published_version: int = 0


class DosingRuleCreate(BaseModel):
    rule_type: str
    label: str | None = None
    formula_numerator: Decimal | None = None
    formula_denominator: Decimal | None = Field(default=Decimal("1"))
    formula_per_kg: bool = True
    weight_min_kg: Decimal | None = None
    weight_max_kg: Decimal | None = None
    weight_min_inclusive: bool = True
    weight_max_inclusive: bool = True
    output_value: Decimal | None = None
    output_unit: str = "mg"
    min_output: Decimal | None = None
    max_output: Decimal | None = None
    sort_order: int = 0
    is_active: bool = True


class DosingBundleOut(BaseModel):
    profiles: list[DosingProfileOut]
    draft_rules: list[DosingRuleOut]
    open_gaps_count: int


class PublishDosingOut(BaseModel):
    published_version: int
