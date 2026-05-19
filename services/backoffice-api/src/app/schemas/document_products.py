from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import PaginatedResponse


class ProductDocumentLinkCreate(BaseModel):
    document_id: UUID
    is_primary: bool = False


class ProductLinkedDocumentOut(BaseModel):
    document_id: UUID
    title: str
    kind: str
    status: str
    country_iso: str | None = None
    is_primary: bool
    updated_at: datetime


class DocumentLinkedProductOut(BaseModel):
    product_id: UUID
    name: str
    brand: str
    is_primary: bool


class DocumentProductsReplace(BaseModel):
    product_ids: list[UUID] = Field(default_factory=list)
    primary_product_id: UUID | None = None

    @model_validator(mode="after")
    def primary_in_list(self) -> DocumentProductsReplace:
        if (
            self.primary_product_id is not None
            and self.primary_product_id not in self.product_ids
        ):
            raise ValueError("primary_product_id debe estar en product_ids")
        return self


ProductLinkedDocumentsResponse = PaginatedResponse[ProductLinkedDocumentOut]


class DocumentLinkedProductsList(BaseModel):
    items: list[DocumentLinkedProductOut]
