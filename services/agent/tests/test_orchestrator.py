"""Tests del orquestador: branches answered / blocked / low_confidence / no_match."""

from __future__ import annotations

import uuid

import pytest

from biomont_common.schemas.knowledge import DocumentKind, HybridChunkHit
from biomont_common.schemas.rag import RagAnswer

from app.agent.graph.graph import GraphOutput, GraphPipeline
from app.agent.orchestrator import (
    AgentOrchestrator,
    PipelineOutput,
    _render_answer,
    effective_retrieval_similarity_threshold,
    maybe_product_confirmation_reply,
)

from tests.conftest import (
    FakeActivePrompt,
    FakeConversationRepository,
    FakeRtcRepository,
    FakeRtcUser,
    FakeSystemPromptRepository,
    FakeWhatsAppClient,
)


class _StaticGraphPipeline(GraphPipeline):
    def __init__(self, output: GraphOutput) -> None:
        super().__init__(compiled=object())
        self._output = output

    async def run(self, **_kwargs) -> GraphOutput:
        return self._output


def _build_orchestrator(*, graph_output: GraphOutput, rtc_user: FakeRtcUser | None):
    rtc_users = {rtc_user.phone_e164: rtc_user} if rtc_user else {}
    conv = FakeConversationRepository()
    return (
        AgentOrchestrator(
            rtc_repository=FakeRtcRepository(rtc_users),  # type: ignore[arg-type]
            conversation_repository=conv,  # type: ignore[arg-type]
            system_prompt_repository=FakeSystemPromptRepository(
                FakeActivePrompt(version=1, content="System prompt v1.")
            ),  # type: ignore[arg-type]
            pipeline=_StaticGraphPipeline(graph_output),  # type: ignore[arg-type]
            whatsapp_client=FakeWhatsAppClient(),  # type: ignore[arg-type]
            similarity_threshold=0.75,
            rag_vector_weight=0.7,
        ),
        conv,
    )


def _graph_output_stub(**kwargs: object) -> GraphOutput:
    defaults: dict[str, object] = {
        "retrieved": [],
        "top_similarity": 0.0,
        "answer_text": None,
        "citations": [],
        "intent": None,
        "product_id": None,
        "product_name": None,
        "product_inherited": False,
        "ambiguous_candidates": [],
        "graph_trace": [],
        "error": None,
    }
    defaults.update(kwargs)
    return GraphOutput(**defaults)  # type: ignore[arg-type]


def _answered_graph_output(
    *,
    doc_id: uuid.UUID,
    title: str,
    answer_text: str,
    top_similarity: float = 0.88,
) -> GraphOutput:
    return _graph_output_stub(
        retrieved=[
            HybridChunkHit(
                chunk_id=uuid.uuid4(),
                document_id=doc_id,
                document_title=title,
                product_id=None,
                kind=DocumentKind.bitacora,
                chunk_index=0,
                section_type="protocol",
                content="contexto",
                country_iso="PE",
                final_score=top_similarity,
            )
        ],
        top_similarity=top_similarity,
        answer_text=answer_text,
        citations=[
            {
                "document_id": str(doc_id),
                "document_title": title,
                "similarity": top_similarity,
            }
        ],
    )


def test_maybe_product_confirmation_none_when_not_answered() -> None:
    pid = uuid.uuid4()
    go = _graph_output_stub(
        product_id=pid,
        product_name="Proteggo M",
        product_inherited=False,
    )
    assert (
        maybe_product_confirmation_reply(decision="no_match", graph_output=go)
        is None
    )


def test_maybe_product_confirmation_none_without_product_id() -> None:
    go = _graph_output_stub(product_id=None, product_name="Algo")
    assert maybe_product_confirmation_reply(decision="answered", graph_output=go) is None


def test_maybe_product_confirmation_resolved_vs_inherited() -> None:
    pid = uuid.uuid4()
    resolved = _graph_output_stub(
        product_id=pid,
        product_name="Proteggo M",
        product_inherited=False,
    )
    inherited = _graph_output_stub(
        product_id=pid,
        product_name="Proteggo M",
        product_inherited=True,
    )
    r = maybe_product_confirmation_reply(decision="answered", graph_output=resolved)
    assert r is not None and "Proteggo M" in r and "referencia" in r
    i = maybe_product_confirmation_reply(decision="answered", graph_output=inherited)
    assert i is not None and "Proteggo M" in i and "sigo usando" in i


def test_effective_similarity_threshold_adjusts_for_graph_fusion_cap() -> None:
    assert effective_retrieval_similarity_threshold(
        configured_threshold=0.75,
        rag_vector_weight=0.7,
    ) == pytest.approx(0.7)
    assert effective_retrieval_similarity_threshold(
        configured_threshold=0.55,
        rag_vector_weight=0.7,
    ) == pytest.approx(0.55)


def test_render_answer_lists_document_titles_without_similarity() -> None:
    answer = RagAnswer(
        answer="Dosis recomendada.",
        citations=[
            {
                "document_id": str(uuid.uuid4()),
                "document_title": "Ficha tecnica X",
                "similarity": 0.91,
            }
        ],
    )
    rendered = _render_answer(answer)
    assert "Ficha tecnica X" in rendered
    assert "Fuentes:" in rendered
    assert "similitud" not in rendered.lower()


@pytest.mark.asyncio
async def test_orchestrator_blocks_unauthorized_phone() -> None:
    graph_output = _graph_output_stub()
    orchestrator, conv = _build_orchestrator(graph_output=graph_output, rtc_user=None)

    result = await orchestrator.handle_incoming_message(
        from_phone_e164="+999111", text_body="hola",
    )

    assert result.decision == "blocked"
    assert any(d["decision"] == "blocked" for d in conv.decisions)
    assert conv.messages == []
    assert conv.tickets == []


@pytest.mark.asyncio
async def test_orchestrator_no_match_creates_ticket(fake_rtc_user) -> None:
    graph_output = _graph_output_stub()
    orchestrator, conv = _build_orchestrator(
        graph_output=graph_output, rtc_user=fake_rtc_user
    )

    result = await orchestrator.handle_incoming_message(
        from_phone_e164=fake_rtc_user.phone_e164,
        text_body="que dosis tiene producto Z?",
    )

    assert result.decision == "no_match"
    assert len(conv.tickets) == 1
    assert conv.tickets[0]["ticket_type"] == "no_info"
    assert any(d["decision"] == "no_match" for d in conv.decisions)


@pytest.mark.asyncio
async def test_orchestrator_answered_persists_citations(fake_rtc_user, fake_chunk_hits) -> None:
    doc_id = fake_chunk_hits[0].document_id
    graph_output = _answered_graph_output(
        doc_id=doc_id,
        title=fake_chunk_hits[0].document_title,
        answer_text="0.2 mg/kg subcutanea.",
        top_similarity=fake_chunk_hits[0].similarity,
    )

    orchestrator, conv = _build_orchestrator(
        graph_output=graph_output, rtc_user=fake_rtc_user
    )

    result = await orchestrator.handle_incoming_message(
        from_phone_e164=fake_rtc_user.phone_e164,
        text_body="dosis del producto X?",
    )

    assert result.decision == "answered"
    assert "Ficha producto X" in result.reply_text
    assert "Fuentes:" in result.reply_text
    assert "similitud" not in result.reply_text.lower()
    assistant_messages = [m for m in conv.messages if m["role"] == "assistant"]
    assert assistant_messages
    assert assistant_messages[0]["citations"]


@pytest.mark.asyncio
async def test_orchestrator_low_confidence_when_pipeline_has_no_citations(
    fake_rtc_user, fake_hybrid_chunks
) -> None:
    graph_output = _graph_output_stub(
        retrieved=fake_hybrid_chunks,
        top_similarity=fake_hybrid_chunks[0].final_score,
        answer_text=None,
        citations=[],
        error="missing_citations",
    )

    orchestrator, conv = _build_orchestrator(
        graph_output=graph_output, rtc_user=fake_rtc_user
    )
    result = await orchestrator.handle_incoming_message(
        from_phone_e164=fake_rtc_user.phone_e164,
        text_body="...",
    )

    assert result.decision == "low_confidence"
    assert len(conv.tickets) == 1
    assert conv.tickets[0]["ticket_type"] == "low_confidence"


@pytest.mark.asyncio
async def test_orchestrator_playground_skips_whatsapp(fake_rtc_user) -> None:
    graph_output = _graph_output_stub()
    rtc_users = {fake_rtc_user.phone_e164: fake_rtc_user}
    conv = FakeConversationRepository()
    wa = FakeWhatsAppClient()
    orchestrator = AgentOrchestrator(
        rtc_repository=FakeRtcRepository(rtc_users),  # type: ignore[arg-type]
        conversation_repository=conv,  # type: ignore[arg-type]
        system_prompt_repository=FakeSystemPromptRepository(
            FakeActivePrompt(version=1, content="System prompt v1.")
        ),  # type: ignore[arg-type]
        pipeline=_StaticGraphPipeline(graph_output),  # type: ignore[arg-type]
        whatsapp_client=wa,  # type: ignore[arg-type]
        similarity_threshold=0.75,
    )

    result = await orchestrator.handle_playground_message(
        rtc_user_id=fake_rtc_user.id,
        text_body="hola desde playground",
    )

    assert result.decision == "no_match"
    assert not wa.sent
