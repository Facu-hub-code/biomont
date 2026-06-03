#!/usr/bin/env python3
"""Carga perfiles y reglas de dosis desde sección DOSIFICACIÓN de fichas técnicas (spec 011).

Extrae la lógica documentada en `knowledge_chunks` (section_type=dosing_table) y tablas
de presentación cuando el ETL no preservó celdas de las tablas PDF.

Idempotente por producto+especie: borra borradores, recrea reglas y publica.

Uso:
    DATABASE_URL=... python scripts/seed_ft_dosing_catalog.py
    railway run python scripts/seed_ft_dosing_catalog.py
    python scripts/seed_ft_dosing_catalog.py --dry-run
    python scripts/seed_ft_dosing_catalog.py --only "Marvo 20,Protego 3M"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for base in (here.parent, *here.parents):
        if (base / "services" / "common" / "src").is_dir():
            return base
    return here.parent.parent


_REPO_ROOT = _repo_root()
sys.path.insert(0, str(_REPO_ROOT / "services" / "common" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "services" / "backoffice-api" / "src"))

from biomont_common.db.dosing_repository import DosingRepository  # noqa: E402
from biomont_common.db.pool import create_pool  # noqa: E402
from biomont_common.dosing.calculator import calculate_dose  # noqa: E402

from app.db.dosing_admin_repository import DosingAdminRepository  # noqa: E402


def _formula(
    num: str,
    den: str,
    *,
    unit: str,
    label: str,
    per_kg: bool = False,
) -> dict[str, Any]:
    return {
        "rule_type": "formula",
        "label": label,
        "formula_numerator": Decimal(num),
        "formula_denominator": Decimal(den),
        "formula_per_kg": per_kg,
        "output_unit": unit,
        "sort_order": 0,
    }


def _band(
    lo: str,
    hi: str,
    out: str,
    *,
    unit: str = "mg",
    label: str,
    sort_order: int = 0,
    min_inclusive: bool = True,
    max_inclusive: bool = True,
) -> dict[str, Any]:
    return {
        "rule_type": "weight_band",
        "label": label,
        "weight_min_kg": Decimal(lo),
        "weight_max_kg": Decimal(hi),
        "weight_min_inclusive": min_inclusive,
        "weight_max_inclusive": max_inclusive,
        "output_value": Decimal(out),
        "output_unit": unit,
        "sort_order": sort_order,
    }


def _fluralaner_3m_bands() -> list[dict[str, Any]]:
    """FT Proteggo 3M §9 — presentaciones 112.5–1400 mg por banda de peso."""
    specs = [
        ("2", "4.5", "112.5", "PROTEGGO 3M 112.5 mg", True),
        ("4.5", "10", "250", "PROTEGGO 3M 250 mg", False),
        ("10", "20", "500", "PROTEGGO 3M 500 mg", False),
        ("20", "40", "1000", "PROTEGGO 3M 1000 mg", False),
        ("40", "56", "1400", "PROTEGGO 3M 1400 mg", False),
    ]
    return [
        _band(lo, hi, mg, label=label, sort_order=i, min_inclusive=min_inc)
        for i, (lo, hi, mg, label, min_inc) in enumerate(specs)
    ]


def _fluralaner_m_bands() -> list[dict[str, Any]]:
    """FT Proteggo M §9 — presentaciones 45–560 mg."""
    specs = [
        ("2", "4.5", "45", "PROTEGGO M 45 mg", True),
        ("4.5", "10", "100", "PROTEGGO M 100 mg", False),
        ("10", "20", "200", "PROTEGGO M 200 mg", False),
        ("20", "40", "400", "PROTEGGO M 400 mg", False),
        ("40", "56", "560", "PROTEGGO M 560 mg", False),
    ]
    return [
        _band(lo, hi, mg, label=label, sort_order=i, min_inclusive=min_inc)
        for i, (lo, hi, mg, label, min_inc) in enumerate(specs)
    ]


def _imperia_bands() -> list[dict[str, Any]]:
    """FT Imperia §9 — sarolaner 10/20/40/80 mg por banda."""
    specs = [
        ("2.5", "5", "10", "IMPERIA 10 mg", True),
        ("5", "10", "20", "IMPERIA 20 mg", False),
        ("10", "20", "40", "IMPERIA 40 mg", False),
        ("20", "40", "80", "IMPERIA 80 mg", False),
    ]
    return [
        _band(lo, hi, mg, label=label, sort_order=i, min_inclusive=min_inc)
        for i, (lo, hi, mg, label, min_inc) in enumerate(specs)
    ]


@dataclass(frozen=True)
class ProfileSeed:
    species: str
    supports: bool
    min_weight_kg: Decimal | None
    max_weight_kg: Decimal | None
    min_age_weeks: int | None = None
    notes: str = ""
    rules: list[dict[str, Any]] = field(default_factory=list)
    completeness: str = "complete"  # complete | not_applicable


@dataclass(frozen=True)
class ProductSeed:
    name: str
    profiles: list[ProfileSeed]
    skip_if_published: bool = False


CATALOG: list[ProductSeed] = [
    ProductSeed(
        "Marvo 20",
        [
            ProfileSeed(
                "canine",
                True,
                Decimal("1.3"),
                Decimal("60"),
                notes="FT §9: 1 tableta/10 kg/día (2 mg/kg marbofloxacino). Perros y gatos.",
                rules=[
                    _formula(
                        "1",
                        "10",
                        unit="tablets",
                        label="1 comp/10 kg — FT §9",
                        per_kg=True,
                    ),
                ],
            ),
            ProfileSeed(
                "feline",
                True,
                Decimal("1.3"),
                Decimal("15"),
                notes="FT §9: misma regla práctica 1 comp/10 kg en gatos.",
                rules=[
                    _formula(
                        "1",
                        "10",
                        unit="tablets",
                        label="1 comp/10 kg — FT §9",
                        per_kg=True,
                    ),
                ],
            ),
        ],
    ),
    ProductSeed(
        "Kuagula",
        [
            ProfileSeed(
                "canine",
                True,
                Decimal("1"),
                Decimal("90"),
                notes="FT §9: 1–1.5 mL/10 kg (se usa 1 mL/10 kg como dosis estándar).",
                rules=[
                    _formula(
                        "1",
                        "10",
                        unit="ml",
                        label="1 mL/10 kg — FT §9",
                        per_kg=True,
                    ),
                ],
            ),
            ProfileSeed(
                "feline",
                True,
                Decimal("1"),
                Decimal("15"),
                notes="FT §9: 1 mL/10 kg felinos.",
                rules=[
                    _formula(
                        "1",
                        "10",
                        unit="ml",
                        label="1 mL/10 kg — FT §9",
                        per_kg=True,
                    ),
                ],
            ),
        ],
    ),
    ProductSeed(
        "Oppia Solucion Inyectable",
        [
            ProfileSeed(
                "canine",
                True,
                Decimal("1"),
                Decimal("90"),
                notes="FT §9: 0.4–0.8 mL/10 kg (2–4 mg/kg); dosis media 0.6 mL/10 kg.",
                rules=[
                    _formula(
                        "0.6",
                        "10",
                        unit="ml",
                        label="0.6 mL/10 kg (media 0.4–0.8) — FT §9",
                        per_kg=True,
                    ),
                ],
            ),
            ProfileSeed(
                "feline",
                True,
                Decimal("1"),
                Decimal("15"),
                notes="FT §9: misma pauta perros y gatos.",
                rules=[
                    _formula(
                        "0.6",
                        "10",
                        unit="ml",
                        label="0.6 mL/10 kg — FT §9",
                        per_kg=True,
                    ),
                ],
            ),
        ],
    ),
    ProductSeed(
        "itrapet",
        [
            ProfileSeed(
                "canine",
                True,
                Decimal("2"),
                Decimal("80"),
                notes="FT §9: 1 comp/10–20 kg → 1 comp/15 kg como dosis práctica central.",
                rules=[
                    _formula(
                        "1",
                        "15",
                        unit="tablets",
                        label="1 comp/15 kg (rango FT 10–20 kg) — FT §9",
                        per_kg=True,
                    ),
                ],
            ),
            ProfileSeed(
                "feline",
                True,
                Decimal("1"),
                Decimal("15"),
                notes="FT §9: pautas específicas por micosis; 5–10 mg/kg → usar 1 comp/15 kg práctico.",
                rules=[
                    _formula(
                        "1",
                        "15",
                        unit="tablets",
                        label="1 comp/15 kg (aprox. 5 mg/kg) — FT §9",
                        per_kg=True,
                    ),
                ],
            ),
        ],
    ),
    ProductSeed(
        "mascotabs",
        [
            ProfileSeed(
                "canine",
                True,
                Decimal("1"),
                Decimal("90"),
                notes="FT §8: <10 kg → 1/2 comp/día; ≥10 kg → 1 comp/día.",
                rules=[
                    _band(
                        "0",
                        "10",
                        "0.5",
                        unit="tablets",
                        label="1/2 tableta/día (<10 kg)",
                        sort_order=0,
                        max_inclusive=False,
                    ),
                    _band(
                        "10",
                        "200",
                        "1",
                        unit="tablets",
                        label="1 tableta/día (≥10 kg)",
                        sort_order=1,
                        min_inclusive=True,
                    ),
                ],
            ),
        ],
    ),
    ProductSeed(
        "Protego 3M",
        [
            ProfileSeed(
                "canine",
                True,
                Decimal("2"),
                Decimal("56"),
                min_age_weeks=8,
                notes="FT §9: tabla fluralaner 25–56 mg/kg; presentaciones 112.5–1400 mg.",
                rules=_fluralaner_3m_bands(),
            ),
        ],
    ),
    ProductSeed(
        "Protego M",
        [
            ProfileSeed(
                "canine",
                True,
                Decimal("2"),
                Decimal("56"),
                min_age_weeks=8,
                notes="FT §9: tabla fluralaner ≥10 mg/kg; presentaciones 45–560 mg.",
                rules=_fluralaner_m_bands(),
            ),
        ],
    ),
    ProductSeed(
        "Imperia",
        [
            ProfileSeed(
                "canine",
                True,
                Decimal("2.5"),
                Decimal("40"),
                notes="FT §9: sarolaner 2–4 mg/kg; presentaciones 10–80 mg.",
                rules=_imperia_bands(),
            ),
        ],
    ),
    ProductSeed(
        "Opruix",
        [
            ProfileSeed(
                "canine",
                True,
                Decimal("3"),
                Decimal("60"),
                notes="FT §9: 0.4–0.6 mg oclacitinib/kg; se usa 0.5 mg/kg como dosis media.",
                rules=[
                    _formula(
                        "0.5",
                        "1",
                        unit="mg",
                        label="0.5 mg/kg (rango FT 0.4–0.6) — FT §9",
                        per_kg=True,
                    ),
                ],
            ),
        ],
    ),
    ProductSeed(
        "Tulabiot",
        [
            ProfileSeed(
                "bovine",
                True,
                Decimal("40"),
                Decimal("1000"),
                notes="FT §9: dosis única 1 mL/40 kg (bovinos, porcinos, ovinos, caprinos).",
                rules=[
                    _formula(
                        "1",
                        "40",
                        unit="ml",
                        label="1 mL/40 kg — FT §9",
                        per_kg=True,
                    ),
                ],
            ),
            ProfileSeed(
                "porcine",
                True,
                Decimal("40"),
                Decimal("300"),
                notes="FT §9: 1 mL/40 kg porcinos.",
                rules=[
                    _formula(
                        "1",
                        "40",
                        unit="ml",
                        label="1 mL/40 kg — FT §9",
                        per_kg=True,
                    ),
                ],
            ),
        ],
    ),
    ProductSeed(
        "Florbiomizona",
        [
            ProfileSeed(
                "bovine",
                True,
                Decimal("10"),
                Decimal("800"),
                notes="FT §9: bovinos 1 mL/10 kg p.v.",
                rules=[
                    _formula(
                        "1",
                        "10",
                        unit="ml",
                        label="1 mL/10 kg — FT §9",
                        per_kg=True,
                    ),
                ],
            ),
            ProfileSeed(
                "porcine",
                True,
                Decimal("10"),
                Decimal("300"),
                notes="FT §9: porcinos 1 mL/10 kg p.v.",
                rules=[
                    _formula(
                        "1",
                        "10",
                        unit="ml",
                        label="1 mL/10 kg — FT §9",
                        per_kg=True,
                    ),
                ],
            ),
        ],
    ),
    ProductSeed(
        "Tilozona",
        [
            ProfileSeed(
                "bovine",
                True,
                Decimal("15"),
                Decimal("800"),
                notes="FT §9: 1 mL/15 kg (bovinos, porcinos, ovinos, caprinos, camélidos).",
                rules=[
                    _formula(
                        "1",
                        "15",
                        unit="ml",
                        label="1 mL/15 kg — FT §9",
                        per_kg=True,
                    ),
                ],
            ),
        ],
    ),
    ProductSeed(
        "Aumentha ATP NF",
        [
            ProfileSeed(
                "porcine",
                True,
                Decimal("10"),
                Decimal("300"),
                notes="FT §9: porcinos 1 mL/10 kg p.v.",
                rules=[
                    _formula(
                        "1",
                        "10",
                        unit="ml",
                        label="1 mL/10 kg — FT §9",
                        per_kg=True,
                    ),
                ],
            ),
            ProfileSeed(
                "bovine",
                False,
                None,
                None,
                notes="FT §9: bovinos 10–15 mL/animal (no por kg); cálculo por kg no aplica.",
                rules=[],
                completeness="not_applicable",
            ),
        ],
    ),
    # Sin cálculo por peso (dosis fija por animal o sin sección DOSIFICACIÓN útil)
    ProductSeed(
        "Hepatin",
        [
            ProfileSeed(
                "bovine",
                False,
                None,
                None,
                notes="FT §9: mL fijos por animal/especie, no por kg.",
                rules=[],
                completeness="not_applicable",
            ),
        ],
    ),
    ProductSeed(
        "Semental",
        [
            ProfileSeed(
                "bovine",
                False,
                None,
                None,
                notes="FT §9: mL por animal, no escala por kg.",
                rules=[],
                completeness="not_applicable",
            ),
        ],
    ),
    ProductSeed(
        "Racion",
        [
            ProfileSeed(
                "bovine",
                False,
                None,
                None,
                notes="FT §8: gramos/animal/día con alimento, no por kg corporal.",
                rules=[],
                completeness="not_applicable",
            ),
        ],
    ),
    ProductSeed(
        "Gigantol ADE",
        [
            ProfileSeed(
                "bovine",
                False,
                None,
                None,
                notes="Sin sección DOSIFICACIÓN indexada en ficha técnica.",
                rules=[],
                completeness="not_applicable",
            ),
        ],
    ),
    ProductSeed(
        "Serentis",
        [],
        skip_if_published=True,
    ),
]


async def _resolve_product(conn, name: str) -> UUID | None:
    row = await conn.fetchrow(
        "SELECT id FROM public.products WHERE lower(name) = lower($1)",
        name,
    )
    return row["id"] if row else None


async def _resolve_ft_doc(conn, product_id: UUID) -> UUID | None:
    row = await conn.fetchrow(
        """
        SELECT d.id FROM public.documents d
        JOIN public.document_products dp ON dp.document_id = d.id
        WHERE dp.product_id = $1 AND d.kind = 'ficha_tecnica'
        ORDER BY d.updated_at DESC NULLS LAST
        LIMIT 1
        """,
        product_id,
    )
    return row["id"] if row else None


async def _seed_profile(
    admin: DosingAdminRepository,
    conn,
    *,
    product_id: UUID,
    product_name: str,
    doc_id: UUID | None,
    profile: ProfileSeed,
    dry_run: bool,
) -> None:
    if not profile.supports and not profile.rules:
        if dry_run:
            print(f"    [{profile.species}] not_applicable (sin reglas)")
            return
        profile_id = await admin.upsert_profile(
            product_id=product_id,
            species=profile.species,
            supports_dose_calculation=False,
            min_age_weeks=None,
            max_age_weeks=None,
            min_weight_kg=None,
            max_weight_kg=None,
            updated_by=None,
        )
        await conn.execute(
            """
            UPDATE public.product_dosing_profiles
            SET completeness_status = $2,
                completeness_notes = $3,
                source_document_id = COALESCE($4, source_document_id),
                updated_at = now()
            WHERE id = $1
            """,
            profile_id,
            profile.completeness,
            profile.notes,
            doc_id,
        )
        print(f"    [{profile.species}] {profile.completeness}")
        return

    if dry_run:
        print(
            f"    [{profile.species}] {len(profile.rules)} reglas "
            f"({profile.min_weight_kg}–{profile.max_weight_kg} kg)"
        )
        return

    profile_id = await admin.upsert_profile(
        product_id=product_id,
        species=profile.species,
        supports_dose_calculation=True,
        min_age_weeks=profile.min_age_weeks,
        max_age_weeks=None,
        min_weight_kg=profile.min_weight_kg,
        max_weight_kg=profile.max_weight_kg,
        updated_by=None,
    )
    await conn.execute(
        """
        UPDATE public.product_dosing_profiles
        SET source_document_id = COALESCE($2, source_document_id),
            completeness_notes = $3
        WHERE id = $1
        """,
        profile_id,
        doc_id,
        profile.notes,
    )
    await conn.execute(
        """
        DELETE FROM public.product_dosing_rules
        WHERE profile_id = $1 AND published_version = 0
        """,
        profile_id,
    )
    for rule in profile.rules:
        await admin.create_rule(profile_id, rule)
    version = await admin.publish_profile(profile_id, published_by=None)
    print(f"    [{profile.species}] publicado v{version} ({len(profile.rules)} reglas)")


async def _verify_sample(
    repo: DosingRepository, product_id: UUID, name: str, species: str, weight: str
) -> None:
    profile = await repo.get_published_profile(product_id, species)
    if profile is None or not profile.supports_dose_calculation:
        return
    rules = await repo.list_published_rules(profile.id, profile.published_version)
    outcome = calculate_dose(
        profile=profile,
        rules=rules,
        product_id=product_id,
        product_name=name,
        weight_kg=Decimal(weight),
        species=species,
    )
    print(f"    verify {species} {weight}kg -> {outcome}")


async def main(dry_run: bool, only: set[str] | None) -> None:
    pool = create_pool()
    await pool.start()
    admin = DosingAdminRepository(pool)
    repo = DosingRepository(pool)
    seeded = 0
    try:
        for entry in CATALOG:
            if only and entry.name.lower() not in {n.lower() for n in only}:
                continue
            async with pool.acquire() as conn:
                product_id = await _resolve_product(conn, entry.name)
                if product_id is None:
                    print(f"SKIP {entry.name}: producto no encontrado")
                    continue
                if entry.skip_if_published and not dry_run:
                    row = await conn.fetchrow(
                        """
                        SELECT completeness_status, published_version
                        FROM public.product_dosing_profiles
                        WHERE product_id = $1 AND species = 'canine'
                        """,
                        product_id,
                    )
                    if row and row["published_version"] > 0:
                        print(f"SKIP {entry.name}: ya publicado v{row['published_version']}")
                        continue
                doc_id = await _resolve_ft_doc(conn, product_id)
            print(f"\n{entry.name} ({product_id})")
            if not entry.profiles:
                continue
            for prof in entry.profiles:
                async with pool.acquire() as conn:
                    await _seed_profile(
                        admin,
                        conn,
                        product_id=product_id,
                        product_name=entry.name,
                        doc_id=doc_id,
                        profile=prof,
                        dry_run=dry_run,
                    )
            seeded += 1
            if not dry_run and entry.name == "Marvo 20":
                await _verify_sample(repo, product_id, entry.name, "canine", "25")
            if not dry_run and entry.name == "Protego 3M":
                await _verify_sample(repo, product_id, entry.name, "canine", "25")
            if not dry_run and entry.name == "Tulabiot":
                await _verify_sample(repo, product_id, entry.name, "bovine", "450")
    finally:
        await pool.stop()
    print(f"\nListo: {seeded} productos procesados.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--only",
        help="Nombres separados por coma (ej. 'Marvo 20,Protego 3M')",
    )
    args = parser.parse_args()
    only_set = None
    if args.only:
        only_set = {n.strip() for n in args.only.split(",") if n.strip()}
    asyncio.run(main(dry_run=args.dry_run, only=only_set))
