"""Endpoints de dosis estructuradas por producto."""

from __future__ import annotations

from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_audit, get_dosing, get_products, require_roles
from app.db.audit_repository import AuditRepository
from app.db.dosing_admin_repository import DosingAdminRepository
from app.db.product_admin_repository import ProductAdminRepository
from app.schemas.auth import CurrentUser
from app.schemas.dosing import (
    DosingBundleOut,
    DosingProfileOut,
    DosingProfileUpsert,
    DosingRuleCreate,
    DosingRuleOut,
    PublishDosingOut,
)

router = APIRouter(prefix="/products", tags=["dosing"])


def _profile_out(row) -> DosingProfileOut:
    return DosingProfileOut(**asdict(row))


def _rule_out(row) -> DosingRuleOut:
    return DosingRuleOut(**asdict(row))


@router.get("/{product_id}/dosing", response_model=DosingBundleOut)
async def get_product_dosing(
    product_id: UUID,
    dosing: DosingAdminRepository = Depends(get_dosing),
    products: ProductAdminRepository = Depends(get_products),
    _: CurrentUser = Depends(require_roles("admin", "scientist", "viewer")),
) -> DosingBundleOut:
    if await products.get_product(product_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    profiles = await dosing.list_profiles(product_id)
    draft_rules: list = []
    for p in profiles:
        draft_rules.extend(await dosing.list_draft_rules(p.id))
    gaps = await dosing.open_gaps_count(product_id)
    return DosingBundleOut(
        profiles=[_profile_out(p) for p in profiles],
        draft_rules=[_rule_out(r) for r in draft_rules],
        open_gaps_count=gaps,
    )


@router.put("/{product_id}/dosing/profile", response_model=DosingProfileOut)
async def upsert_dosing_profile(
    product_id: UUID,
    payload: DosingProfileUpsert,
    dosing: DosingAdminRepository = Depends(get_dosing),
    audit: AuditRepository = Depends(get_audit),
    current: CurrentUser = Depends(require_roles("admin", "scientist")),
) -> DosingProfileOut:
    profile_id = await dosing.upsert_profile(
        product_id=product_id,
        species=payload.species,
        supports_dose_calculation=payload.supports_dose_calculation,
        min_age_weeks=payload.min_age_weeks,
        max_age_weeks=payload.max_age_weeks,
        min_weight_kg=payload.min_weight_kg,
        max_weight_kg=payload.max_weight_kg,
        updated_by=current.id,
    )
    await audit.record(
        actor_id=current.id,
        entity="product_dosing_profiles",
        entity_id=profile_id,
        action="upsert",
        after=payload.model_dump(mode="json"),
    )
    profiles = await dosing.list_profiles(product_id)
    match = next((p for p in profiles if p.id == profile_id), None)
    if match is None:
        raise HTTPException(status_code=500)
    return _profile_out(match)


@router.post(
    "/{product_id}/dosing/profiles/{profile_id}/rules",
    response_model=DosingRuleOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_dosing_rule(
    product_id: UUID,
    profile_id: UUID,
    payload: DosingRuleCreate,
    dosing: DosingAdminRepository = Depends(get_dosing),
    audit: AuditRepository = Depends(get_audit),
    current: CurrentUser = Depends(require_roles("admin", "scientist")),
) -> DosingRuleOut:
    rule_id = await dosing.create_rule(profile_id, payload.model_dump(mode="json"))
    await audit.record(
        actor_id=current.id,
        entity="product_dosing_rules",
        entity_id=rule_id,
        action="create",
        after=payload.model_dump(mode="json"),
    )
    rules = await dosing.list_draft_rules(profile_id)
    match = next((r for r in rules if r.id == rule_id), None)
    if match is None:
        raise HTTPException(status_code=500)
    return _rule_out(match)


@router.delete(
    "/{product_id}/dosing/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_dosing_rule(
    product_id: UUID,
    rule_id: UUID,
    dosing: DosingAdminRepository = Depends(get_dosing),
    audit: AuditRepository = Depends(get_audit),
    current: CurrentUser = Depends(require_roles("admin", "scientist")),
) -> None:
    deleted = await dosing.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await audit.record(
        actor_id=current.id,
        entity="product_dosing_rules",
        entity_id=rule_id,
        action="delete",
    )


@router.post(
    "/{product_id}/dosing/profiles/{profile_id}/publish",
    response_model=PublishDosingOut,
)
async def publish_dosing_profile(
    product_id: UUID,
    profile_id: UUID,
    dosing: DosingAdminRepository = Depends(get_dosing),
    audit: AuditRepository = Depends(get_audit),
    current: CurrentUser = Depends(require_roles("admin")),
) -> PublishDosingOut:
    try:
        version = await dosing.publish_profile(profile_id, published_by=current.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    await audit.record(
        actor_id=current.id,
        entity="product_dosing_profiles",
        entity_id=profile_id,
        action="publish",
        after={"published_version": version},
    )
    return PublishDosingOut(published_version=version)
