"""Endpoints CRUD de productos y aliases."""

from __future__ import annotations

from dataclasses import asdict
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_audit, get_products, require_roles
from app.db.audit_repository import AuditRepository
from app.db.product_admin_repository import ProductAdminRepository
from app.schemas.auth import CurrentUser
from app.schemas.products import (
    ProductAliasCreate,
    ProductAliasListResponse,
    ProductAliasOut,
    ProductAliasUpdate,
    ProductCreate,
    ProductListResponse,
    ProductOut,
    ProductUpdate,
)

router = APIRouter(prefix="/products", tags=["products"])


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    safe_page = max(1, page)
    safe_page_size = min(max(1, page_size), 100)
    return safe_page, safe_page_size


def _to_product_out(row) -> ProductOut:
    return ProductOut(**asdict(row))


def _to_alias_out(row) -> ProductAliasOut:
    return ProductAliasOut(**asdict(row))


@router.get("", response_model=ProductListResponse)
async def list_products(
    products: ProductAdminRepository = Depends(get_products),
    _: CurrentUser = Depends(require_roles("admin", "scientist", "viewer")),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> ProductListResponse:
    safe_page, safe_size = _pagination(page, page_size)
    total, rows = await products.list_products(page=safe_page, page_size=safe_size)
    return ProductListResponse(
        items=[_to_product_out(row) for row in rows],
        page=safe_page,
        page_size=safe_size,
        total=total,
    )


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    products: ProductAdminRepository = Depends(get_products),
    audit: AuditRepository = Depends(get_audit),
    current: CurrentUser = Depends(require_roles("admin", "scientist")),
) -> ProductOut:
    try:
        product_id = await products.create_product(
            name=payload.name,
            brand=payload.brand,
            duration_type=payload.duration_type,
            description=payload.description,
            country_iso=payload.country_iso.upper() if payload.country_iso else None,
        )
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un producto con el mismo nombre y pais.",
        ) from exc
    row = await products.get_product(product_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    await audit.record(
        actor_id=current.id,
        entity="products",
        entity_id=product_id,
        action="create",
        after=payload.model_dump(),
    )
    return _to_product_out(row)


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: UUID,
    products: ProductAdminRepository = Depends(get_products),
    _: CurrentUser = Depends(require_roles("admin", "scientist", "viewer")),
) -> ProductOut:
    row = await products.get_product(product_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _to_product_out(row)


@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    products: ProductAdminRepository = Depends(get_products),
    audit: AuditRepository = Depends(get_audit),
    current: CurrentUser = Depends(require_roles("admin", "scientist")),
) -> ProductOut:
    existing = await products.get_product(product_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        return _to_product_out(existing)
    if "country_iso" in fields and fields["country_iso"] is not None:
        fields["country_iso"] = fields["country_iso"].upper()
    try:
        updated = await products.update_product(
            product_id,
            name=fields.get("name"),
            brand=fields.get("brand"),
            duration_type=fields.get("duration_type"),
            description=fields.get("description"),
            country_iso=fields.get("country_iso"),
        )
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un producto con el mismo nombre y pais.",
        ) from exc
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await audit.record(
        actor_id=current.id,
        entity="products",
        entity_id=product_id,
        action="update",
        before={k: getattr(existing, k) for k in fields},
        after=fields,
    )
    return _to_product_out(updated)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_product(
    product_id: UUID,
    products: ProductAdminRepository = Depends(get_products),
    audit: AuditRepository = Depends(get_audit),
    current: CurrentUser = Depends(require_roles("admin")),
) -> None:
    existing = await products.get_product(product_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        deleted = await products.delete_product(product_id)
    except asyncpg.ForeignKeyViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar el producto por referencias activas.",
        ) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await audit.record(
        actor_id=current.id,
        entity="products",
        entity_id=product_id,
        action="delete",
        before=asdict(existing),
    )


@router.get("/{product_id}/aliases", response_model=ProductAliasListResponse)
async def list_product_aliases(
    product_id: UUID,
    products: ProductAdminRepository = Depends(get_products),
    _: CurrentUser = Depends(require_roles("admin", "scientist", "viewer")),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> ProductAliasListResponse:
    product = await products.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    safe_page, safe_size = _pagination(page, page_size)
    total, rows = await products.list_aliases(
        product_id,
        page=safe_page,
        page_size=safe_size,
    )
    return ProductAliasListResponse(
        items=[_to_alias_out(row) for row in rows],
        page=safe_page,
        page_size=safe_size,
        total=total,
    )


@router.post(
    "/{product_id}/aliases",
    response_model=ProductAliasOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_product_alias(
    product_id: UUID,
    payload: ProductAliasCreate,
    products: ProductAdminRepository = Depends(get_products),
    audit: AuditRepository = Depends(get_audit),
    current: CurrentUser = Depends(require_roles("admin", "scientist")),
) -> ProductAliasOut:
    product = await products.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        alias_id = await products.create_alias(
            product_id=product_id,
            alias=payload.alias,
            source=payload.source,
            confidence=payload.confidence,
        )
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese alias ya existe para el producto.",
        ) from exc
    row = await products.get_alias(product_id, alias_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    await audit.record(
        actor_id=current.id,
        entity="product_aliases",
        entity_id=alias_id,
        action="create",
        after=payload.model_dump(),
    )
    return _to_alias_out(row)


@router.patch("/{product_id}/aliases/{alias_id}", response_model=ProductAliasOut)
async def update_product_alias(
    product_id: UUID,
    alias_id: UUID,
    payload: ProductAliasUpdate,
    products: ProductAdminRepository = Depends(get_products),
    audit: AuditRepository = Depends(get_audit),
    current: CurrentUser = Depends(require_roles("admin", "scientist")),
) -> ProductAliasOut:
    existing = await products.get_alias(product_id, alias_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        return _to_alias_out(existing)
    try:
        row = await products.update_alias(
            product_id=product_id,
            alias_id=alias_id,
            alias=fields.get("alias"),
            source=fields.get("source"),
            confidence=fields.get("confidence"),
        )
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese alias ya existe para el producto.",
        ) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await audit.record(
        actor_id=current.id,
        entity="product_aliases",
        entity_id=alias_id,
        action="update",
        before={k: getattr(existing, k) for k in fields},
        after=fields,
    )
    return _to_alias_out(row)


@router.delete(
    "/{product_id}/aliases/{alias_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_product_alias(
    product_id: UUID,
    alias_id: UUID,
    products: ProductAdminRepository = Depends(get_products),
    audit: AuditRepository = Depends(get_audit),
    current: CurrentUser = Depends(require_roles("admin", "scientist")),
) -> None:
    existing = await products.get_alias(product_id, alias_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    deleted = await products.delete_alias(product_id=product_id, alias_id=alias_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await audit.record(
        actor_id=current.id,
        entity="product_aliases",
        entity_id=alias_id,
        action="delete",
        before=asdict(existing),
    )
