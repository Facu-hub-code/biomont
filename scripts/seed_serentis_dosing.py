#!/usr/bin/env python3
"""Carga perfil y reglas de dosis de Serentis desde la ficha técnica (spec 011).

Ficha (sección 9. DOSIFICACIÓN):
  Perros y gatos: 1 mL / 10 kg de peso (1 mg maropitant/kg), hasta 5 días.

Idempotente: borra borradores previos del perfil y recrea regla + publica.

Uso:
    DATABASE_URL=... python scripts/seed_serentis_dosing.py
    railway run python scripts/seed_serentis_dosing.py
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "services" / "common" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "services" / "backoffice-api" / "src"))

from biomont_common.db.pool import create_pool  # noqa: E402
from biomont_common.dosing.calculator import calculate_dose  # noqa: E402
from biomont_common.db.dosing_repository import DosingRepository  # noqa: E402

from app.db.dosing_admin_repository import DosingAdminRepository  # noqa: E402

SERENTIS_NAME = "Serentis"
FT_TITLE_FRAGMENT = "SERENTIS"

# Ficha técnica §9: 1 mL por cada 10 kg (0,1 mL/kg).
FORMULA_RULE = {
    "rule_type": "formula",
    "label": "1 mL/10 kg (1 mg maropitant/kg) — FT §9",
    "formula_numerator": Decimal("1"),
    "formula_denominator": Decimal("10"),
    "formula_per_kg": True,
    "output_unit": "ml",
    "sort_order": 0,
}

SPECIES_PROFILES = (
    ("canine", Decimal("1"), Decimal("90")),
    ("feline", Decimal("1"), Decimal("15")),
)


async def _resolve_serentis(conn) -> tuple[UUID, UUID | None]:
    row = await conn.fetchrow(
        """
        SELECT id FROM public.products
        WHERE lower(name) = lower($1)
        """,
        SERENTIS_NAME,
    )
    if row is None:
        raise SystemExit(f"Producto '{SERENTIS_NAME}' no encontrado. Correr bootstrap_products.")
    product_id = row["id"]
    doc = await conn.fetchrow(
        """
        SELECT d.id FROM public.documents d
        JOIN public.document_products dp ON dp.document_id = d.id
        WHERE dp.product_id = $1 AND d.kind = 'ficha_tecnica'
          AND upper(d.title) LIKE '%' || $2 || '%'
        ORDER BY d.updated_at DESC NULLS LAST
        LIMIT 1
        """,
        product_id,
        FT_TITLE_FRAGMENT,
    )
    return product_id, doc["id"] if doc else None


async def _seed_profile(
    admin: DosingAdminRepository,
    conn,
    *,
    product_id: UUID,
    species: str,
    min_kg: Decimal,
    max_kg: Decimal,
    source_document_id: UUID | None,
    dry_run: bool,
) -> None:
    profile_id = await admin.upsert_profile(
        product_id=product_id,
        species=species,
        supports_dose_calculation=True,
        min_age_weeks=None,
        max_age_weeks=None,
        min_weight_kg=min_kg,
        max_weight_kg=max_kg,
        updated_by=None,
    )
    if not dry_run:
        await conn.execute(
            """
            UPDATE public.product_dosing_profiles
            SET source_document_id = COALESCE($2, source_document_id),
                completeness_notes = $3
            WHERE id = $1
            """,
            profile_id,
            source_document_id,
            "FT Serentis §9 DOSIFICACIÓN: 1 mL/10 kg, perros y gatos.",
        )
        await conn.execute(
            """
            DELETE FROM public.product_dosing_rules
            WHERE profile_id = $1 AND published_version = 0
            """,
            profile_id,
        )

    print(f"  [{species}] profile_id={profile_id}")
    if dry_run:
        print(f"    would create rule: {FORMULA_RULE}")
        return

    await admin.create_rule(profile_id, FORMULA_RULE)
    version = await admin.publish_profile(profile_id, published_by=None)
    print(f"    publicado v{version}")


async def _verify(repo: DosingRepository, product_id: UUID) -> None:
    for species, weight in (("canine", "25"), ("feline", "4")):
        profile = await repo.get_published_profile(product_id, species)
        if profile is None:
            print(f"  VERIFY FAIL: sin perfil {species}")
            continue
        rules = await repo.list_published_rules(profile.id, profile.published_version)
        outcome = calculate_dose(
            profile=profile,
            rules=rules,
            product_id=product_id,
            product_name=SERENTIS_NAME,
            weight_kg=Decimal(weight),
            species=species,
        )
        print(f"  VERIFY {species} {weight} kg -> {outcome}")


async def main(dry_run: bool) -> None:
    pool = create_pool()
    await pool.start()
    try:
        async with pool.acquire() as conn:
            product_id, doc_id = await _resolve_serentis(conn)
        print(f"Producto {SERENTIS_NAME} ({product_id})")
        if doc_id:
            print(f"  Ficha técnica: {doc_id}")

        admin = DosingAdminRepository(pool)
        for species, min_kg, max_kg in SPECIES_PROFILES:
            async with pool.acquire() as conn:
                await _seed_profile(
                    admin,
                    conn,
                    product_id=product_id,
                    species=species,
                    min_kg=min_kg,
                    max_kg=max_kg,
                    source_document_id=doc_id,
                    dry_run=dry_run,
                )

        if not dry_run:
            await _verify(DosingRepository(pool), product_id)
    finally:
        await pool.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
