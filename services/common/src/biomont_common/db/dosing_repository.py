"""Repositorio de dosis estructuradas (spec 011)."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import asyncpg

from biomont_common.db.pool import DatabasePool
from biomont_common.schemas.dosing import (
    CompletenessStatus,
    DosingOutputUnit,
    DosingProfile,
    DosingRule,
    DosingRuleType,
)


def _dec(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


class DosingRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def get_published_profile(
        self,
        product_id: UUID,
        species: str,
    ) -> DosingProfile | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, product_id, species, supports_dose_calculation,
                       min_age_weeks, max_age_weeks, min_weight_kg, max_weight_kg,
                       completeness_status, published_version
                FROM public.product_dosing_profiles
                WHERE product_id = $1 AND species = $2
                """,
                product_id,
                species,
            )
        if row is None:
            return None
        return DosingProfile(
            id=row["id"],
            product_id=row["product_id"],
            species=row["species"],
            supports_dose_calculation=row["supports_dose_calculation"],
            min_age_weeks=row["min_age_weeks"],
            max_age_weeks=row["max_age_weeks"],
            min_weight_kg=_dec(row["min_weight_kg"]),
            max_weight_kg=_dec(row["max_weight_kg"]),
            completeness_status=CompletenessStatus(row["completeness_status"]),
            published_version=row["published_version"],
        )

    async def list_published_rules(self, profile_id: UUID, version: int) -> list[DosingRule]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, profile_id, rule_type, label,
                       formula_numerator, formula_denominator, formula_per_kg,
                       weight_min_kg, weight_max_kg,
                       weight_min_inclusive, weight_max_inclusive,
                       output_value, output_unit, min_output, max_output,
                       sort_order, is_active, published_version
                FROM public.product_dosing_rules
                WHERE profile_id = $1 AND published_version = $2 AND is_active = true
                ORDER BY sort_order, weight_min_kg NULLS LAST
                """,
                profile_id,
                version,
            )
        return [_row_to_rule(r) for r in rows]

    async def list_species_for_product(self, product_id: UUID) -> list[str]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT species FROM public.product_dosing_profiles
                WHERE product_id = $1 AND supports_dose_calculation = true
                ORDER BY species
                """,
                product_id,
            )
        return [r["species"] for r in rows]


def _row_to_rule(row: asyncpg.Record) -> DosingRule:
    return DosingRule(
        id=row["id"],
        profile_id=row["profile_id"],
        rule_type=DosingRuleType(row["rule_type"]),
        label=row["label"],
        formula_numerator=_dec(row["formula_numerator"]),
        formula_denominator=_dec(row["formula_denominator"]),
        formula_per_kg=row["formula_per_kg"],
        weight_min_kg=_dec(row["weight_min_kg"]),
        weight_max_kg=_dec(row["weight_max_kg"]),
        weight_min_inclusive=row["weight_min_inclusive"],
        weight_max_inclusive=row["weight_max_inclusive"],
        output_value=_dec(row["output_value"]),
        output_unit=DosingOutputUnit(row["output_unit"]),
        min_output=_dec(row["min_output"]),
        max_output=_dec(row["max_output"]),
        sort_order=row["sort_order"],
        is_active=row["is_active"],
        published_version=row["published_version"],
    )
