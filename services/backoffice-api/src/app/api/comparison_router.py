"""Endpoints del comparador comercial."""

from __future__ import annotations

from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.api.dependencies import (
    get_audit,
    get_comparison,
    get_products,
    require_roles,
)
from app.db.audit_repository import AuditRepository
from app.db.comparison_admin_repository import ComparisonAdminRepository
from app.db.product_admin_repository import ProductAdminRepository
from app.schemas.auth import CurrentUser
from app.schemas.comparison import (
    ComparisonColumnListResponse,
    ComparisonColumnOut,
    ComparisonColumnPriorityUpdate,
    ComparisonSetOut,
    CompetitorCreate,
    CompetitorListResponse,
    CompetitorOut,
    ImportComparisonOut,
    PublishComparisonOut,
)
from app.services.commercial_comparison_import import import_commercial_xlsx

router = APIRouter(tags=["comparison"])


def _competitor_out(row) -> CompetitorOut:
    return CompetitorOut(**asdict(row))


@router.get("/competitors", response_model=CompetitorListResponse)
async def list_competitors(
    comparison: ComparisonAdminRepository = Depends(get_comparison),
    _: CurrentUser = Depends(require_roles("admin", "scientist", "viewer")),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> CompetitorListResponse:
    total, rows = await comparison.list_competitors(page=page, page_size=page_size)
    return CompetitorListResponse(
        items=[_competitor_out(r) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/competitors",
    response_model=CompetitorOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_competitor(
    payload: CompetitorCreate,
    comparison: ComparisonAdminRepository = Depends(get_comparison),
    audit: AuditRepository = Depends(get_audit),
    current: CurrentUser = Depends(require_roles("admin", "scientist")),
) -> CompetitorOut:
    comp_id = await comparison.create_competitor(
        name=payload.name,
        brand=payload.brand,
        is_internal=payload.is_internal,
        linked_product_id=payload.linked_product_id,
    )
    total, rows = await comparison.list_competitors(page=1, page_size=1000)
    match = next((r for r in rows if r.id == comp_id), None)
    if match is None:
        raise HTTPException(status_code=500)
    await audit.record(
        actor_id=current.id,
        entity="competitors",
        entity_id=comp_id,
        action="create",
        after=payload.model_dump(mode="json"),
    )
    return _competitor_out(match)


@router.get(
    "/products/{product_id}/comparison",
    response_model=ComparisonSetOut | None,
)
async def get_product_comparison(
    product_id: UUID,
    comparison: ComparisonAdminRepository = Depends(get_comparison),
    products: ProductAdminRepository = Depends(get_products),
    _: CurrentUser = Depends(require_roles("admin", "scientist", "viewer")),
) -> ComparisonSetOut | None:
    if await products.get_product(product_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    row = await comparison.get_set_by_product(product_id)
    if row is None:
        return None
    return ComparisonSetOut(**asdict(row))


@router.get(
    "/products/{product_id}/comparison/columns",
    response_model=ComparisonColumnListResponse,
)
async def list_product_comparison_columns(
    product_id: UUID,
    comparison: ComparisonAdminRepository = Depends(get_comparison),
    products: ProductAdminRepository = Depends(get_products),
    _: CurrentUser = Depends(require_roles("admin", "scientist", "viewer")),
) -> ComparisonColumnListResponse:
    if await products.get_product(product_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    set_row = await comparison.get_set_by_product(product_id)
    if set_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    rows = await comparison.list_columns(set_row.id)
    return ComparisonColumnListResponse(
        items=[ComparisonColumnOut(**asdict(r)) for r in rows]
    )


@router.put(
    "/products/{product_id}/comparison/columns",
    response_model=ComparisonColumnListResponse,
)
async def update_product_comparison_columns(
    product_id: UUID,
    payload: ComparisonColumnPriorityUpdate,
    comparison: ComparisonAdminRepository = Depends(get_comparison),
    products: ProductAdminRepository = Depends(get_products),
    audit: AuditRepository = Depends(get_audit),
    current: CurrentUser = Depends(require_roles("admin", "scientist")),
) -> ComparisonColumnListResponse:
    if await products.get_product(product_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    set_row = await comparison.get_set_by_product(product_id)
    if set_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        await comparison.update_column_priorities(
            set_row.id,
            priority_keys=payload.priority_column_keys,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    rows = await comparison.list_columns(set_row.id)
    await audit.record(
        actor_id=current.id,
        entity="commercial_comparison_columns",
        entity_id=set_row.id,
        action="update_priorities",
        after={"priority_column_keys": payload.priority_column_keys},
    )
    return ComparisonColumnListResponse(
        items=[ComparisonColumnOut(**asdict(r)) for r in rows]
    )


@router.post(
    "/products/{product_id}/comparison/import",
    response_model=ImportComparisonOut,
)
async def import_product_comparison(
    product_id: UUID,
    file: UploadFile = File(...),
    comparison: ComparisonAdminRepository = Depends(get_comparison),
    products: ProductAdminRepository = Depends(get_products),
    audit: AuditRepository = Depends(get_audit),
    current: CurrentUser = Depends(require_roles("admin", "scientist")),
) -> ImportComparisonOut:
    product = await products.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    raw = await file.read()
    try:
        result = await import_commercial_xlsx(
            repo=comparison,
            subject_product_id=product_id,
            subject_product_name=product.name,
            file_bytes=raw,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    await audit.record(
        actor_id=current.id,
        entity="commercial_comparison_sets",
        entity_id=product_id,
        action="import",
        after=result,
    )
    return ImportComparisonOut(**result)


@router.post(
    "/products/{product_id}/comparison/publish",
    response_model=PublishComparisonOut,
)
async def publish_product_comparison(
    product_id: UUID,
    comparison: ComparisonAdminRepository = Depends(get_comparison),
    audit: AuditRepository = Depends(get_audit),
    current: CurrentUser = Depends(require_roles("admin")),
) -> PublishComparisonOut:
    set_row = await comparison.get_set_by_product(product_id)
    if set_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        version = await comparison.publish_set(set_row.id, published_by=current.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    await audit.record(
        actor_id=current.id,
        entity="commercial_comparison_sets",
        entity_id=set_row.id,
        action="publish",
        after={"published_version": version},
    )
    return PublishComparisonOut(published_version=version)
