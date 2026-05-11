"""Endpoints CRUD + upload de documentos."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from biomont_common.db.pool import DatabasePool
from biomont_common.db.rag_repository import RagRepository
from biomont_common.integrations.openai_factory import build_embeddings
from biomont_common.logging import get_logger

from app.api.dependencies import (
    get_audit,
    get_current_user,
    get_documents,
    get_pool,
    get_rag,
    require_roles,
)
from app.db.audit_repository import AuditRepository
from app.db.document_repository import DocumentRepository
from app.integrations.docling_converter import DoclingPdfConverter
from app.schemas.auth import CurrentUser
from app.schemas.documents import (
    DocumentDetail,
    DocumentSummary,
    DocumentUpdate,
)
from app.services.etl_pipeline import DocumentIngestService

_logger = get_logger("api.documents")

router = APIRouter(prefix="/documents", tags=["documents"])


def _summary(row) -> DocumentSummary:
    return DocumentSummary(**{k: v for k, v in asdict(row).items() if k != "markdown"})


def _detail(row) -> DocumentDetail:
    return DocumentDetail(**asdict(row))


@router.get("", response_model=list[DocumentSummary])
async def list_documents(
    _: Annotated[CurrentUser, Depends(get_current_user)],
    documents: Annotated[DocumentRepository, Depends(get_documents)],
) -> list[DocumentSummary]:
    rows = await documents.list_documents()
    return [_summary(row) for row in rows]


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: UUID,
    _: Annotated[CurrentUser, Depends(get_current_user)],
    documents: Annotated[DocumentRepository, Depends(get_documents)],
) -> DocumentDetail:
    row = await documents.get_document(document_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _detail(row)


@router.post(
    "",
    response_model=DocumentDetail,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    pool: Annotated[DatabasePool, Depends(get_pool)],
    documents: Annotated[DocumentRepository, Depends(get_documents)],
    rag: Annotated[RagRepository, Depends(get_rag)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    current: Annotated[
        CurrentUser, Depends(require_roles("admin", "scientist"))
    ],
    file: UploadFile = File(...),
    title: str = Form(...),
    product_name: str | None = Form(default=None),
    country_iso: str | None = Form(default=None),
    language: str = Form(default="es"),
) -> DocumentDetail:
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="only application/pdf is accepted",
        )

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="empty file",
        )

    converter = DoclingPdfConverter()
    embeddings = build_embeddings()
    pipeline = DocumentIngestService(
        pool=pool,
        documents=documents,
        rag=rag,
        converter=converter,
        embeddings=embeddings,
    )

    result = await pipeline.ingest_pdf(
        pdf_bytes=pdf_bytes,
        original_filename=file.filename,
        title=title,
        product_name=product_name,
        country_iso=country_iso,
        language=language,
        uploaded_by=current.id,
    )

    document = await documents.get_document(result.document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    await audit.record(
        actor_id=current.id,
        entity="documents",
        entity_id=document.id,
        action="upload",
        after={
            "title": document.title,
            "country_iso": document.country_iso,
            "chunks": result.chunks_persisted,
        },
    )
    return _detail(document)


@router.patch("/{document_id}", response_model=DocumentDetail)
async def update_document(
    document_id: UUID,
    payload: DocumentUpdate,
    documents: Annotated[DocumentRepository, Depends(get_documents)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    current: Annotated[
        CurrentUser, Depends(require_roles("admin", "scientist"))
    ],
) -> DocumentDetail:
    existing = await documents.get_document(document_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    fields = payload.model_dump(exclude_unset=True)
    if "classification" in fields:
        fields["classification"] = fields["classification"] or {}

    updated = await documents.update_document(document_id, fields=fields)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    await audit.record(
        actor_id=current.id,
        entity="documents",
        entity_id=document_id,
        action="update",
        before={k: getattr(existing, k) for k in fields},
        after=fields,
    )
    return _detail(updated)
