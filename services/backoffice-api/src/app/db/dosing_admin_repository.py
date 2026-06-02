"""Administracion de dosis estructuradas (spec 011)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg

from biomont_common.db.pool import DatabasePool


@dataclass(frozen=True, slots=True)
class DosingProfileRow:
    id: UUID
    product_id: UUID
    species: str
    supports_dose_calculation: bool
    min_age_weeks: int | None
    max_age_weeks: int | None
    min_weight_kg: Decimal | None
    max_weight_kg: Decimal | None
    completeness_status: str
    completeness_notes: str | None
    published_version: int


@dataclass(frozen=True, slots=True)
class DosingRuleRow:
    id: UUID
    profile_id: UUID
    rule_type: str
    label: str | None
    formula_numerator: Decimal | None
    formula_denominator: Decimal | None
    formula_per_kg: bool
    weight_min_kg: Decimal | None
    weight_max_kg: Decimal | None
    weight_min_inclusive: bool
    weight_max_inclusive: bool
    output_value: Decimal | None
    output_unit: str
    min_output: Decimal | None
    max_output: Decimal | None
    sort_order: int
    is_active: bool
    published_version: int


class DosingAdminRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def list_profiles(self, product_id: UUID) -> list[DosingProfileRow]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, product_id, species, supports_dose_calculation,
                       min_age_weeks, max_age_weeks, min_weight_kg, max_weight_kg,
                       completeness_status, completeness_notes, published_version
                FROM public.product_dosing_profiles
                WHERE product_id = $1
                ORDER BY species
                """,
                product_id,
            )
        return [_profile_row(r) for r in rows]

    async def upsert_profile(
        self,
        *,
        product_id: UUID,
        species: str,
        supports_dose_calculation: bool,
        min_age_weeks: int | None,
        max_age_weeks: int | None,
        min_weight_kg: Decimal | None,
        max_weight_kg: Decimal | None,
        updated_by: UUID | None,
    ) -> UUID:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.product_dosing_profiles (
                    product_id, species, supports_dose_calculation,
                    min_age_weeks, max_age_weeks, min_weight_kg, max_weight_kg,
                    updated_by, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now())
                ON CONFLICT (product_id, species) DO UPDATE SET
                    supports_dose_calculation = EXCLUDED.supports_dose_calculation,
                    min_age_weeks = EXCLUDED.min_age_weeks,
                    max_age_weeks = EXCLUDED.max_age_weeks,
                    min_weight_kg = EXCLUDED.min_weight_kg,
                    max_weight_kg = EXCLUDED.max_weight_kg,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = now()
                RETURNING id
                """,
                product_id,
                species,
                supports_dose_calculation,
                min_age_weeks,
                max_age_weeks,
                min_weight_kg,
                max_weight_kg,
                updated_by,
            )
        return row["id"]

    async def list_draft_rules(self, profile_id: UUID) -> list[DosingRuleRow]:
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
                WHERE profile_id = $1 AND published_version = 0
                ORDER BY sort_order, weight_min_kg NULLS LAST
                """,
                profile_id,
            )
        return [_rule_row(r) for r in rows]

    async def create_rule(self, profile_id: UUID, data: dict[str, Any]) -> UUID:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.product_dosing_rules (
                    profile_id, rule_type, label,
                    formula_numerator, formula_denominator, formula_per_kg,
                    weight_min_kg, weight_max_kg,
                    weight_min_inclusive, weight_max_inclusive,
                    output_value, output_unit, min_output, max_output,
                    sort_order, is_active, published_version
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, 0
                )
                RETURNING id
                """,
                profile_id,
                data["rule_type"],
                data.get("label"),
                data.get("formula_numerator"),
                data.get("formula_denominator"),
                data.get("formula_per_kg", True),
                data.get("weight_min_kg"),
                data.get("weight_max_kg"),
                data.get("weight_min_inclusive", True),
                data.get("weight_max_inclusive", True),
                data.get("output_value"),
                data.get("output_unit", "mg"),
                data.get("min_output"),
                data.get("max_output"),
                data.get("sort_order", 0),
                data.get("is_active", True),
            )
        return row["id"]

    async def delete_rule(self, rule_id: UUID) -> bool:
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM public.product_dosing_rules
                WHERE id = $1 AND published_version = 0
                """,
                rule_id,
            )
        return result.endswith("1")

    async def open_gaps_count(self, product_id: UUID) -> int:
        async with self._pool.acquire() as conn:
            val = await conn.fetchval(
                """
                SELECT COUNT(*) FROM public.product_dosing_gaps
                WHERE product_id = $1 AND resolved_at IS NULL
                  AND severity = 'blocking'
                """,
                product_id,
            )
        return int(val or 0)

    async def publish_profile(
        self, profile_id: UUID, *, published_by: UUID | None
    ) -> int:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                profile = await conn.fetchrow(
                    """
                    SELECT id, product_id, species, published_version
                    FROM public.product_dosing_profiles WHERE id = $1
                    FOR UPDATE
                    """,
                    profile_id,
                )
                if profile is None:
                    raise ValueError("profile_not_found")

                new_version = profile["published_version"] + 1
                draft_rules = await conn.fetch(
                    """
                    SELECT * FROM public.product_dosing_rules
                    WHERE profile_id = $1 AND published_version = 0 AND is_active = true
                    """,
                    profile_id,
                )
                if not draft_rules:
                    raise ValueError("no_draft_rules")

                for rule in draft_rules:
                    await conn.execute(
                        """
                        INSERT INTO public.product_dosing_rules (
                            profile_id, rule_type, label,
                            formula_numerator, formula_denominator, formula_per_kg,
                            weight_min_kg, weight_max_kg,
                            weight_min_inclusive, weight_max_inclusive,
                            output_value, output_unit, min_output, max_output,
                            sort_order, is_active, published_version
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                            $11, $12, $13, $14, $15, $16, $17
                        )
                        """,
                        profile_id,
                        rule["rule_type"],
                        rule["label"],
                        rule["formula_numerator"],
                        rule["formula_denominator"],
                        rule["formula_per_kg"],
                        rule["weight_min_kg"],
                        rule["weight_max_kg"],
                        rule["weight_min_inclusive"],
                        rule["weight_max_inclusive"],
                        rule["output_value"],
                        rule["output_unit"],
                        rule["min_output"],
                        rule["max_output"],
                        rule["sort_order"],
                        rule["is_active"],
                        new_version,
                    )

                snapshot = {
                    "profile_id": str(profile_id),
                    "species": profile["species"],
                    "rules": [dict(r) for r in draft_rules],
                }
                await conn.execute(
                    """
                    INSERT INTO public.product_dosing_versions (
                        product_id, profile_id, version, snapshot, published_by
                    ) VALUES ($1, $2, $3, $4::jsonb, $5)
                    """,
                    profile["product_id"],
                    profile_id,
                    new_version,
                    json.dumps(snapshot, default=str),
                    published_by,
                )
                await conn.execute(
                    """
                    UPDATE public.product_dosing_profiles
                    SET published_version = $2,
                        completeness_status = 'complete',
                        updated_at = now(),
                        updated_by = $3
                    WHERE id = $1
                    """,
                    profile_id,
                    new_version,
                    published_by,
                )
                await conn.execute(
                    """
                    UPDATE public.product_dosing_gaps
                    SET resolved_at = now()
                    WHERE profile_id = $1 AND resolved_at IS NULL
                    """,
                    profile_id,
                )
        return new_version


def _profile_row(row: asyncpg.Record) -> DosingProfileRow:
    return DosingProfileRow(
        id=row["id"],
        product_id=row["product_id"],
        species=row["species"],
        supports_dose_calculation=row["supports_dose_calculation"],
        min_age_weeks=row["min_age_weeks"],
        max_age_weeks=row["max_age_weeks"],
        min_weight_kg=row["min_weight_kg"],
        max_weight_kg=row["max_weight_kg"],
        completeness_status=row["completeness_status"],
        completeness_notes=row["completeness_notes"],
        published_version=row["published_version"],
    )


def _rule_row(row: asyncpg.Record) -> DosingRuleRow:
    return DosingRuleRow(
        id=row["id"],
        profile_id=row["profile_id"],
        rule_type=row["rule_type"],
        label=row["label"],
        formula_numerator=row["formula_numerator"],
        formula_denominator=row["formula_denominator"],
        formula_per_kg=row["formula_per_kg"],
        weight_min_kg=row["weight_min_kg"],
        weight_max_kg=row["weight_max_kg"],
        weight_min_inclusive=row["weight_min_inclusive"],
        weight_max_inclusive=row["weight_max_inclusive"],
        output_value=row["output_value"],
        output_unit=row["output_unit"],
        min_output=row["min_output"],
        max_output=row["max_output"],
        sort_order=row["sort_order"],
        is_active=row["is_active"],
        published_version=row["published_version"],
    )
