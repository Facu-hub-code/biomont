"""Endpoints CRUD + upload de documentos."""

from __future__ import annotations

import json
import os
import time
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

from biomont_common.db.faq_repository import FaqRepository
from biomont_common.db.pool import DatabasePool
from biomont_common.db.product_repository import ProductRepository
from biomont_common.db.rag_repository import RagRepository
from biomont_common.integrations.faq_extractor import FaqExtractor
from biomont_common.integrations.openai_factory import (
    build_chat_model,
    build_embeddings,
)
from biomont_common.logging import get_logger
from biomont_common.schemas.knowledge import DocumentKind

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
from app.integrations.docling_converter import get_docling_pdf_converter
from app.schemas.auth import CurrentUser
from app.schemas.documents import (
    DocumentDetail,
    DocumentSummary,
    DocumentUpdate,
    ReingestResponse,
)
from app.services.etl_pipeline import DocumentIngestService

_logger = get_logger("api.documents")

_DEBUG_LOG_PATH = os.environ.get(
    "CURSOR_DEBUG_LOG_PATH",
    "/Users/facundolorenzo/Documents/SuplaiSales/source/biomont/.cursor/debug-33ab56.log",
)


def _agent_dbg(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    # #region agent log
    try:
        payload = {
            "sessionId": "33ab56",
            "runId": "pre-fix",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass
    # #endregion


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
    # #region agent log
    _agent_dbg(
        "H1",
        "documents_router.list_documents",
        "rows fetched",
        {"count": len(rows)},
    )
    # #endregion
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
    kind: str = Form(default="bitacora"),
    product_id: UUID | None = Form(default=None),
) -> DocumentDetail:
    try:
        DocumentKind(kind)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"kind invalido: {kind!r}. Valores: ficha_tecnica, bitacora, balotario.",
        )
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

    # #region agent log
    _agent_dbg(
        "H2",
        "documents_router.upload_document",
        "starting ingest",
        {
            "content_type": file.content_type,
            "pdf_bytes": len(pdf_bytes),
            "title_len": len(title),
        },
    )
    # #endregion

    converter = get_docling_pdf_converter()
    embeddings = build_embeddings()
    faq_repository = FaqRepository(pool)
    product_repository = ProductRepository(pool)
    faq_extractor = (
        FaqExtractor(chat_model=build_chat_model(temperature=0.0))
        if kind == DocumentKind.balotario.value
        else None
    )
    pipeline = DocumentIngestService(
        pool=pool,
        documents=documents,
        rag=rag,
        converter=converter,
        embeddings=embeddings,
        faq_repository=faq_repository,
        product_repository=product_repository,
        faq_extractor=faq_extractor,
    )

    try:
        result = await pipeline.ingest_pdf(
            pdf_bytes=pdf_bytes,
            original_filename=file.filename,
            title=title,
            product_name=product_name,
            country_iso=country_iso,
            language=language,
            uploaded_by=current.id,
            kind=kind,
            product_id=product_id,
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
        # #region agent log
        _agent_dbg(
            "H2",
            "documents_router.upload_document",
            "ingest finished ok",
            {
                "document_id": str(document.id),
                "status": document.status,
                "chunks": result.chunks_persisted,
            },
        )
        # #endregion
        return _detail(document)
    except Exception as exc:
        # #region agent log
        _agent_dbg(
            "H2",
            "documents_router.upload_document",
            "ingest raised",
            {"exc_type": type(exc).__name__, "exc_msg": str(exc)[:400]},
        )
        # #endregion
        raise


@router.post(
    "/{document_id}/reingest",
    response_model=ReingestResponse,
    status_code=status.HTTP_200_OK,
)
async def reingest_document(
    document_id: UUID,
    pool: Annotated[DatabasePool, Depends(get_pool)],
    documents: Annotated[DocumentRepository, Depends(get_documents)],
    rag: Annotated[RagRepository, Depends(get_rag)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    current: Annotated[CurrentUser, Depends(require_roles("admin"))],
    file: UploadFile = File(...),
    kind: str = Form(...),
    product_id: UUID | None = Form(default=None),
) -> ReingestResponse:
    """Reingiere un documento existente con el schema enriquecido (spec 003).

    Util para migrar el corpus actual a `knowledge_chunks` +
    `document_sections` + `faq_entries` sin necesidad de re-uploadear como
    nuevo documento (lo cual chocaria con `content_sha256 UNIQUE`).

    Solo admins pueden invocarlo (puede modificar datos validados).
    """

    existing = await documents.get_document(document_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    try:
        DocumentKind(kind)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"kind invalido: {kind!r}",
        )

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="empty file",
        )

    converter = get_docling_pdf_converter()
    embeddings = build_embeddings()
    faq_repository = FaqRepository(pool)
    product_repository = ProductRepository(pool)
    faq_extractor = (
        FaqExtractor(chat_model=build_chat_model(temperature=0.0))
        if kind == DocumentKind.balotario.value
        else None
    )

    pipeline = DocumentIngestService(
        pool=pool,
        documents=documents,
        rag=rag,
        converter=converter,
        embeddings=embeddings,
        faq_repository=faq_repository,
        product_repository=product_repository,
        faq_extractor=faq_extractor,
    )

    result = await pipeline.reingest_existing(
        document_id=document_id,
        pdf_bytes=pdf_bytes,
        original_filename=file.filename,
        kind=kind,
        product_id=product_id,
        validated_by=current.id,
        language=existing.language,
    )

    await audit.record(
        actor_id=current.id,
        entity="documents",
        entity_id=document_id,
        action="reingest",
        after={
            "kind": kind,
            "product_id": str(product_id) if product_id else None,
            "knowledge_chunks": result.knowledge_chunks_persisted,
            "sections": result.sections_persisted,
            "faq_entries": result.faq_entries_persisted,
        },
    )

    return ReingestResponse(
        document_id=result.document_id,
        legacy_chunks=result.chunks_persisted,
        knowledge_chunks=result.knowledge_chunks_persisted,
        sections=result.sections_persisted,
        faq_entries=result.faq_entries_persisted,
        markdown_chars=result.markdown_chars,
    )


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
