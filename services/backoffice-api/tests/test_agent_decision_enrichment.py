from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.db.agent_decision_enrichment_repository import (
    DocumentTitleRow,
    KnowledgeChunkRow,
    ProductNameRow,
)
from app.services.agent_decision_enrichment import (
    AgentDecisionEnrichmentService,
    build_chunk_label,
)


def test_build_chunk_label_prefers_topic() -> None:
    assert build_chunk_label(kind="ficha", topic="INDICACIONES") == "ficha · INDICACIONES"


def test_build_chunk_label_section_type() -> None:
    assert (
        build_chunk_label(section_type="clinical", subsection_type="dose")
        == "clinical · dose"
    )


def test_build_chunk_label_index_fallback() -> None:
    assert build_chunk_label(chunk_index=3) == "Chunk #3"


@pytest.fixture()
def enrichment_service() -> tuple[AgentDecisionEnrichmentService, AsyncMock]:
    repo = AsyncMock()
    return AgentDecisionEnrichmentService(repo), repo


@pytest.mark.asyncio
async def test_enrich_retrieved_and_graph_trace(enrichment_service) -> None:
    service, repo = enrichment_service
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    product_id = uuid.uuid4()

    repo.fetch_documents_by_ids.return_value = {
        doc_id: DocumentTitleRow(id=doc_id, title="Imperia Ficha"),
    }
    repo.fetch_knowledge_chunks_by_ids.return_value = {
        chunk_id: KnowledgeChunkRow(
            id=chunk_id,
            document_id=doc_id,
            kind="ficha",
            chunk_index=5,
            section_type=None,
            subsection_type=None,
            topic="INDICACIONES",
            content="Texto del chunk",
        ),
    }
    repo.fetch_products_by_ids.return_value = {
        product_id: ProductNameRow(id=product_id, name="Imperia"),
    }

    result = await service.enrich(
        decision_id=uuid.uuid4(),
        retrieved=[
            {
                "document_id": str(doc_id),
                "chunk_id": str(chunk_id),
                "similarity": 0.88,
            }
        ],
        graph_trace=[
            {
                "node": "ProductResolver",
                "latency_ms": 12,
                "outcome": "resolved",
                "payload": {"product_id": str(product_id), "similarity": 0.9},
            },
            {
                "node": "HybridRetriever",
                "latency_ms": 40,
                "outcome": "retrieved",
                "payload": {
                    "count": 1,
                    "top_scores": [
                        {
                            "chunk_id": str(chunk_id),
                            "vec": 0.8,
                            "bm25": 0.1,
                            "final": 0.75,
                        }
                    ],
                },
            },
        ],
    )

    assert len(result.retrieved_items) == 1
    item = result.retrieved_items[0]
    assert item.document_title == "Imperia Ficha"
    assert "INDICACIONES" in item.chunk_label
    assert item.chunk_content == "Texto del chunk"
    assert item.chunk_found is True

    resolver = result.graph_trace_display[0]
    assert resolver.display["product_name"] == "Imperia"

    hybrid = result.graph_trace_display[1]
    score = hybrid.display["top_scores"][0]
    assert "INDICACIONES" in score["chunk_label"]
    assert score["chunk_content"] == "Texto del chunk"

    repo.fetch_knowledge_chunks_by_ids.assert_awaited_once()
    chunk_arg = repo.fetch_knowledge_chunks_by_ids.await_args.args[0]
    assert chunk_arg == [chunk_id]


@pytest.mark.asyncio
async def test_enrich_missing_chunk(enrichment_service) -> None:
    service, repo = enrichment_service
    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    repo.fetch_documents_by_ids.return_value = {}
    repo.fetch_knowledge_chunks_by_ids.return_value = {}
    repo.fetch_products_by_ids.return_value = {}

    result = await service.enrich(
        decision_id=uuid.uuid4(),
        retrieved=[
            {
                "document_id": str(doc_id),
                "chunk_id": str(chunk_id),
                "similarity": 0.5,
            }
        ],
        graph_trace=[],
    )

    assert result.retrieved_items[0].chunk_found is False
    assert result.retrieved_items[0].chunk_label == "Chunk no encontrado"
    assert result.retrieved_items[0].chunk_content is None
