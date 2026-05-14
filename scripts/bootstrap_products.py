#!/usr/bin/env python3
"""Bootstrap idempotente de `products` + `product_aliases` (spec 003).

Lee `seeds/products.yaml` (versionado), conecta a Postgres via `DATABASE_URL`
y aplica upserts. Tambien:

- Reasigna `documents.product_id` cuando `documents.product_name` matchea
  exactamente con `products.name` (lower).
- Inserta el propio `name` como alias `source='name'` para que el
  ProductResolver lo encuentre sin configuracion extra.

Idempotente: corre N veces sin duplicar nada.

Uso:
    DATABASE_URL=postgres://... python scripts/bootstrap_products.py
    # o
    DATABASE_URL=postgres://... python scripts/bootstrap_products.py \
        --seeds path/to/products.yaml --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

# Permitimos correr el script sin instalar los paquetes con `-e .` agregando
# los src/ al path (esto evita pedirle al operador que instale el paquete).
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "services" / "common" / "src"))

import asyncpg  # noqa: E402  (importa despues de tocar sys.path)
import yaml  # noqa: E402

from biomont_common.db.product_repository import normalize_text  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seeds",
        default=str(_REPO_ROOT / "seeds" / "products.yaml"),
        help="Path al YAML de productos (default: seeds/products.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Loggea las acciones pero no escribe en Postgres.",
    )
    return parser.parse_args()


def _load_seeds(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        print(f"[bootstrap] {path} no existe; nada que hacer.")
        return []
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    products = data.get("products") or []
    if not isinstance(products, list):
        raise SystemExit(
            "[bootstrap] El YAML debe tener una clave 'products' con lista."
        )
    return products


async def _upsert_product(
    conn: asyncpg.Connection,
    *,
    product: dict[str, Any],
    dry_run: bool,
) -> tuple[str, str]:
    """Devuelve (product_id, action)."""

    name = (product.get("name") or "").strip()
    if not name:
        raise SystemExit("[bootstrap] cada producto debe tener 'name'.")

    brand = (product.get("brand") or "Biomont").strip()
    duration_type = (product.get("duration_type") or None)
    description = (product.get("description") or None)
    country_iso = (product.get("country_iso") or None)
    if country_iso:
        country_iso = country_iso.strip().upper()

    if dry_run:
        return ("dry-run", "would_upsert")

    row = await conn.fetchrow(
        """
        INSERT INTO public.products
            (name, brand, duration_type, description, country_iso)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (lower(name), COALESCE(country_iso, 'XX'::char(2)))
        DO UPDATE SET
            brand = EXCLUDED.brand,
            duration_type = COALESCE(EXCLUDED.duration_type, public.products.duration_type),
            description   = COALESCE(EXCLUDED.description,   public.products.description)
        RETURNING id, xmax = 0 AS inserted
        """,
        name,
        brand,
        duration_type,
        description,
        country_iso,
    )
    product_id = str(row["id"])
    action = "inserted" if row["inserted"] else "updated"
    return (product_id, action)


async def _upsert_alias(
    conn: asyncpg.Connection,
    *,
    product_id: str,
    alias: str,
    source: str,
    confidence: float,
    dry_run: bool,
) -> str:
    cleaned = alias.strip()
    if not cleaned:
        return "empty"
    if dry_run:
        return "would_upsert"

    result = await conn.execute(
        """
        INSERT INTO public.product_aliases
            (product_id, alias, source, confidence)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (product_id, normalized_alias) DO NOTHING
        """,
        product_id,
        cleaned,
        source,
        confidence,
    )
    return "inserted" if not result.endswith("0") else "skipped"


async def _reassign_documents(
    conn: asyncpg.Connection,
    *,
    product: dict[str, Any],
    product_id: str,
    dry_run: bool,
) -> int:
    """Asocia `documents.product_id` por match exacto sobre `product_name`."""

    name = product["name"].strip()
    country_iso = (product.get("country_iso") or None)

    if dry_run:
        row = await conn.fetchrow(
            """
            SELECT count(*) AS cnt
            FROM public.documents
            WHERE product_id IS NULL
              AND lower(product_name) = lower($1)
              AND ($2::char(2) IS NULL OR country_iso = $2)
            """,
            name,
            country_iso,
        )
        return int(row["cnt"])

    result = await conn.execute(
        """
        UPDATE public.documents
        SET product_id = $1
        WHERE product_id IS NULL
          AND lower(product_name) = lower($2)
          AND ($3::char(2) IS NULL OR country_iso = $3)
        """,
        product_id,
        name,
        country_iso,
    )
    return int(result.rsplit(" ", 1)[-1])


async def main_async() -> int:
    args = _parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("[bootstrap] ERROR: DATABASE_URL no esta seteada.", file=sys.stderr)
        return 2

    seeds_path = Path(args.seeds)
    seeds = _load_seeds(seeds_path)
    if not seeds:
        print("[bootstrap] sin productos para bootstrappear.")
        return 0

    print(f"[bootstrap] modo: {'dry-run' if args.dry_run else 'apply'}")
    print(f"[bootstrap] productos en YAML: {len(seeds)}")

    conn = await asyncpg.connect(dsn=database_url)
    try:
        for product in seeds:
            product_id, action = await _upsert_product(
                conn, product=product, dry_run=args.dry_run
            )
            aliases_added = 0
            if not args.dry_run:
                # Alias canonico = name (idempotente).
                await _upsert_alias(
                    conn,
                    product_id=product_id,
                    alias=product["name"],
                    source="name",
                    confidence=1.0,
                    dry_run=False,
                )
                # Si hay duration_type, lo agregamos como pista comun.
                duration = product.get("duration_type")
                if duration:
                    await _upsert_alias(
                        conn,
                        product_id=product_id,
                        alias=str(duration),
                        source="bootstrap",
                        confidence=0.6,
                        dry_run=False,
                    )
                for alias in product.get("aliases") or []:
                    res = await _upsert_alias(
                        conn,
                        product_id=product_id,
                        alias=alias,
                        source="bootstrap",
                        confidence=0.9,
                        dry_run=False,
                    )
                    if res == "inserted":
                        aliases_added += 1
            reassigned = await _reassign_documents(
                conn, product=product, product_id=product_id, dry_run=args.dry_run
            )
            print(
                f"[bootstrap] {product['name']!r}: {action} "
                f"(aliases+={aliases_added}, documents_reasigned={reassigned}, "
                f"id={product_id}, normalized={normalize_text(product['name'])!r})"
            )
    finally:
        await conn.close()

    return 0


def main() -> None:
    try:
        rc = asyncio.run(main_async())
    except KeyboardInterrupt:
        rc = 130
    sys.exit(rc)


if __name__ == "__main__":
    main()
