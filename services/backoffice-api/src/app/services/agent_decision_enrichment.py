"""BFF: enriquece retrieved y graph_trace de agent_decisions para el backoffice."""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

from app.db.agent_decision_enrichment_repository import (
    AgentDecisionEnrichmentRepository,
    KnowledgeChunkRow,
)
from app.schemas.agent_decisions import (
    AgentDecisionDetailEnrichment,
    GraphTraceStepDisplay,
    RetrievedItemEnriched,
)

_logger = logging.getLogger(__name__)

_CONTENT_MAX_CHARS = 80 * 1024


def _parse_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def build_chunk_label(
    *,
    kind: str | None = None,
    topic: str | None = None,
    section_type: str | None = None,
    subsection_type: str | None = None,
    chunk_index: int | None = None,
) -> str:
    if topic and str(topic).strip():
        core = str(topic).strip()
    elif section_type:
        core = str(section_type)
        if subsection_type:
            core = f"{core} · {subsection_type}"
    elif chunk_index is not None:
        core = f"Chunk #{chunk_index}"
    else:
        core = "Chunk desconocido"
    if kind:
        return f"{kind} · {core}"
    return core


def _truncate_content(content: str | None) -> tuple[str | None, bool]:
    if content is None:
        return None, False
    if len(content) <= _CONTENT_MAX_CHARS:
        return content, False
    return content[:_CONTENT_MAX_CHARS] + "\n… [truncado]", True


def _chunk_maps(
    chunk: KnowledgeChunkRow | None,
) -> tuple[str, str | None, bool]:
    if chunk is None:
        return "Chunk no encontrado", None, False
    label = build_chunk_label(
        kind=chunk.kind,
        topic=chunk.topic,
        section_type=chunk.section_type,
        subsection_type=chunk.subsection_type,
        chunk_index=chunk.chunk_index,
    )
    content, _ = _truncate_content(chunk.content)
    return label, content, True


class AgentDecisionEnrichmentService:
    def __init__(self, repository: AgentDecisionEnrichmentRepository) -> None:
        self._repository = repository

    async def enrich(
        self,
        *,
        decision_id: UUID,
        retrieved: list[dict[str, Any]],
        graph_trace: list[dict[str, Any]],
    ) -> AgentDecisionDetailEnrichment:
        started = time.perf_counter()
        document_ids: set[UUID] = set()
        chunk_ids: set[UUID] = set()
        product_ids: set[UUID] = set()

        for item in retrieved:
            doc_id = _parse_uuid(item.get("document_id"))
            chunk_id = _parse_uuid(item.get("chunk_id"))
            if doc_id:
                document_ids.add(doc_id)
            if chunk_id:
                chunk_ids.add(chunk_id)

        for step in graph_trace:
            node = step.get("node") or step.get("name")
            payload = step.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            if node == "HybridRetriever":
                for score in payload.get("top_scores") or []:
                    if isinstance(score, dict):
                        cid = _parse_uuid(score.get("chunk_id"))
                        if cid:
                            chunk_ids.add(cid)
            elif node == "ProductResolver":
                pid = _parse_uuid(payload.get("product_id"))
                if pid:
                    product_ids.add(pid)
                for candidate in payload.get("candidates") or []:
                    if isinstance(candidate, dict):
                        cid = _parse_uuid(candidate.get("product_id"))
                        if cid:
                            product_ids.add(cid)

        documents = await self._repository.fetch_documents_by_ids(list(document_ids))
        chunks = await self._repository.fetch_knowledge_chunks_by_ids(list(chunk_ids))
        products = await self._repository.fetch_products_by_ids(list(product_ids))

        retrieved_items = self._build_retrieved_items(retrieved, documents, chunks)
        graph_trace_display = self._build_graph_trace_display(
            graph_trace, chunks, products
        )

        missing_chunks = len(chunk_ids) - len(chunks)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        _logger.debug(
            "agent_decision_enrichment",
            extra={
                "decision_id": str(decision_id),
                "documents_requested": len(document_ids),
                "chunks_requested": len(chunk_ids),
                "chunks_missing": missing_chunks,
                "products_requested": len(product_ids),
                "duration_ms": elapsed_ms,
            },
        )

        return AgentDecisionDetailEnrichment(
            retrieved_items=retrieved_items,
            graph_trace_display=graph_trace_display,
        )

    def _build_retrieved_items(
        self,
        retrieved: list[dict[str, Any]],
        documents: dict,
        chunks: dict[UUID, KnowledgeChunkRow],
    ) -> list[RetrievedItemEnriched]:
        items: list[RetrievedItemEnriched] = []
        for raw in retrieved:
            doc_id = _parse_uuid(raw.get("document_id"))
            chunk_id = _parse_uuid(raw.get("chunk_id"))
            if doc_id is None or chunk_id is None:
                continue
            similarity = raw.get("similarity")
            sim_float = float(similarity) if similarity is not None else None
            doc_row = documents.get(doc_id)
            chunk_row = chunks.get(chunk_id)
            label, content, found = _chunk_maps(chunk_row)
            items.append(
                RetrievedItemEnriched(
                    document_id=doc_id,
                    chunk_id=chunk_id,
                    similarity=sim_float,
                    document_title=doc_row.title if doc_row else None,
                    chunk_label=label,
                    chunk_content=content,
                    chunk_found=found,
                )
            )
        return items

    def _enrich_top_score(self, score: dict[str, Any], chunks: dict) -> dict[str, Any]:
        enriched = dict(score)
        chunk_id = _parse_uuid(score.get("chunk_id"))
        if chunk_id is None:
            enriched["chunk_label"] = "Chunk desconocido"
            enriched["chunk_found"] = False
            return enriched
        chunk_row = chunks.get(chunk_id)
        label, content, found = _chunk_maps(chunk_row)
        enriched["chunk_label"] = label
        enriched["chunk_found"] = found
        if content is not None:
            enriched["chunk_content"] = content
        return enriched

    def _build_graph_trace_display(
        self,
        graph_trace: list[dict[str, Any]],
        chunks: dict[UUID, KnowledgeChunkRow],
        products: dict,
    ) -> list[GraphTraceStepDisplay]:
        steps: list[GraphTraceStepDisplay] = []
        for step in graph_trace:
            node = str(step.get("node") or step.get("name") or "unknown")
            outcome = step.get("outcome")
            latency = step.get("latency_ms")
            latency_ms = float(latency) if latency is not None else None
            payload = step.get("payload")
            payload_dict = payload if isinstance(payload, dict) else {}
            display = self._build_step_display(node, payload_dict, chunks, products)
            steps.append(
                GraphTraceStepDisplay(
                    node=node,
                    outcome=str(outcome) if outcome is not None else None,
                    latency_ms=latency_ms,
                    display=display,
                    payload_raw=payload_dict or None,
                )
            )
        return steps

    def _build_step_display(
        self,
        node: str,
        payload: dict[str, Any],
        chunks: dict[UUID, KnowledgeChunkRow],
        products: dict,
    ) -> dict[str, Any]:
        if node == "ProductResolver":
            display = dict(payload)
            product_id = _parse_uuid(payload.get("product_id"))
            if product_id:
                row = products.get(product_id)
                display["product_name"] = row.name if row else None
            candidates = []
            for candidate in payload.get("candidates") or []:
                if not isinstance(candidate, dict):
                    continue
                enriched = dict(candidate)
                pid = _parse_uuid(candidate.get("product_id"))
                if pid and not enriched.get("name"):
                    row = products.get(pid)
                    if row:
                        enriched["name"] = row.name
                candidates.append(enriched)
            if candidates:
                display["candidates"] = candidates
            return display

        if node == "HybridRetriever":
            display = dict(payload)
            top_scores = []
            for score in payload.get("top_scores") or []:
                if isinstance(score, dict):
                    top_scores.append(self._enrich_top_score(score, chunks))
            if top_scores:
                display["top_scores"] = top_scores
            return display

        return dict(payload)
