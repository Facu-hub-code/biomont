"""Tests del pipeline LCEL del agente."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import RunnableLambda

from biomont_common.schemas.rag import RagAnswer

from app.agent.rag_pipeline import RagPipeline


class _PassthroughStructuredFakeModel(FakeListChatModel):
    """Fake que devuelve un RagAnswer ya construido via structured output."""

    def with_structured_output(self, schema: Any, **_: Any):  # type: ignore[override]
        payload_json = self.responses[0]

        async def _parse(_inputs: dict) -> RagAnswer:
            return RagAnswer.model_validate_json(payload_json)

        return RunnableLambda(_parse)


@pytest.mark.asyncio
async def test_pipeline_returns_answer_with_citations_in_context(
    fake_chunk_hits,
) -> None:
    doc_id = fake_chunk_hits[0].document_id
    expected = RagAnswer(
        answer="La dosis es 0.2 mg/kg.",
        citations=[
            {
                "document_id": str(doc_id),
                "document_title": "Ficha producto X",
                "similarity": 0.92,
            }
        ],
    ).model_dump_json()

    pipeline = RagPipeline(
        rag=_StubRag(fake_chunk_hits),  # type: ignore[arg-type]
        embeddings=_StubEmbeddings(),
        chat_model=_PassthroughStructuredFakeModel(responses=[expected]),
        top_k=3,
    )

    output = await pipeline.run(
        query="dosis del producto X",
        allowed_countries=["PE"],
        system_prompt="Sos el agente.",
    )

    assert output.answer is not None
    assert output.answer.citations
    assert output.answer.citations[0].document_id == doc_id
    assert output.top_similarity == pytest.approx(0.92)


@pytest.mark.asyncio
async def test_pipeline_filters_out_citations_outside_context(
    fake_chunk_hits,
) -> None:
    unrelated = uuid.uuid4()
    expected = RagAnswer(
        answer="texto",
        citations=[
            {
                "document_id": str(unrelated),
                "document_title": "Otro",
                "similarity": 0.5,
            }
        ],
    ).model_dump_json()

    pipeline = RagPipeline(
        rag=_StubRag(fake_chunk_hits),  # type: ignore[arg-type]
        embeddings=_StubEmbeddings(),
        chat_model=_PassthroughStructuredFakeModel(responses=[expected]),
        top_k=3,
    )

    output = await pipeline.run(
        query="...",
        allowed_countries=["PE"],
        system_prompt="...",
    )

    assert output.answer is not None
    assert len(output.answer.citations) == 1
    assert output.answer.citations[0].document_id == fake_chunk_hits[0].document_id


@pytest.mark.asyncio
async def test_pipeline_no_retrieved_returns_empty() -> None:
    pipeline = RagPipeline(
        rag=_StubRag([]),  # type: ignore[arg-type]
        embeddings=_StubEmbeddings(),
        chat_model=_PassthroughStructuredFakeModel(responses=["{}"]),
        top_k=3,
    )
    output = await pipeline.run(
        query="...", allowed_countries=["PE"], system_prompt="...",
    )
    assert output.answer is None
    assert output.top_similarity == 0.0


# ---------------------------------------------------------------------
# Stubs minimos compatibles con la interfaz que usa RagPipeline.
# ---------------------------------------------------------------------
class _StubRag:
    def __init__(self, hits):
        self._hits = hits

    async def search_similar_chunks(self, *, query_embedding, allowed_countries, top_k):
        return self._hits[:top_k]


class _StubEmbeddings:
    async def aembed_query(self, _query):
        return [0.0] * 1536
