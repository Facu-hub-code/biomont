"""Tests del orquestador: branches answered / blocked / low_confidence / no_match."""

from __future__ import annotations

import uuid

import pytest

from biomont_common.schemas.rag import RagAnswer, RetrievedChunk

from app.agent.orchestrator import (
    AgentOrchestrator,
    _render_answer,
    effective_retrieval_similarity_threshold,
)
from app.agent.rag_pipeline import PipelineOutput

from tests.conftest import (
    FakeActivePrompt,
    FakeConversationRepository,
    FakeRtcRepository,
    FakeRtcUser,
    FakeSystemPromptRepository,
    FakeWhatsAppClient,
)


class _StaticPipeline:
    """Pipeline fake que devuelve una PipelineOutput precanada."""

    def __init__(self, output: PipelineOutput) -> None:
        self._output = output

    async def run(self, **_kwargs) -> PipelineOutput:
        return self._output


def _build_orchestrator(*, pipeline_output: PipelineOutput, rtc_user: FakeRtcUser | None):
    rtc_users = {rtc_user.phone_e164: rtc_user} if rtc_user else {}
    conv = FakeConversationRepository()
    return (
        AgentOrchestrator(
            rtc_repository=FakeRtcRepository(rtc_users),  # type: ignore[arg-type]
            conversation_repository=conv,  # type: ignore[arg-type]
            system_prompt_repository=FakeSystemPromptRepository(
                FakeActivePrompt(version=1, content="System prompt v1.")
            ),  # type: ignore[arg-type]
            pipeline=_StaticPipeline(pipeline_output),  # type: ignore[arg-type]
            whatsapp_client=FakeWhatsAppClient(),  # type: ignore[arg-type]
            similarity_threshold=0.75,
        ),
        conv,
    )


def test_effective_similarity_threshold_adjusts_for_graph_fusion_cap() -> None:
    assert effective_retrieval_similarity_threshold(
        configured_threshold=0.75,
        pipeline_uses_graph=True,
        rag_vector_weight=0.7,
    ) == pytest.approx(0.7)
    assert effective_retrieval_similarity_threshold(
        configured_threshold=0.55,
        pipeline_uses_graph=True,
        rag_vector_weight=0.7,
    ) == pytest.approx(0.55)
    assert effective_retrieval_similarity_threshold(
        configured_threshold=0.75,
        pipeline_uses_graph=False,
        rag_vector_weight=0.7,
    ) == pytest.approx(0.75)


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
    output = PipelineOutput(
        retrieved=[], top_similarity=0.0, answer=None, raw_answer_text=None
    )
    orchestrator, conv = _build_orchestrator(pipeline_output=output, rtc_user=None)

    result = await orchestrator.handle_incoming_message(
        from_phone_e164="+999111", text_body="hola",
    )

    assert result.decision == "blocked"
    assert any(d["decision"] == "blocked" for d in conv.decisions)
    assert conv.messages == []
    assert conv.tickets == []


@pytest.mark.asyncio
async def test_orchestrator_no_match_creates_ticket(fake_rtc_user) -> None:
    output = PipelineOutput(
        retrieved=[],
        top_similarity=0.0,
        answer=None,
        raw_answer_text=None,
    )
    orchestrator, conv = _build_orchestrator(
        pipeline_output=output, rtc_user=fake_rtc_user
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
    retrieved = [
        RetrievedChunk(
            chunk_id=h.chunk_id,
            document_id=h.document_id,
            document_title=h.document_title,
            country_iso=h.country_iso,
            chunk_index=h.chunk_index,
            content=h.content,
            similarity=h.similarity,
        )
        for h in fake_chunk_hits
    ]
    answer = RagAnswer(
        answer="0.2 mg/kg subcutanea.",
        citations=[
            {
                "document_id": str(retrieved[0].document_id),
                "document_title": retrieved[0].document_title,
                "similarity": retrieved[0].similarity,
            }
        ],
    )
    output = PipelineOutput(
        retrieved=retrieved,
        top_similarity=retrieved[0].similarity,
        answer=answer,
        raw_answer_text=answer.answer,
    )

    orchestrator, conv = _build_orchestrator(
        pipeline_output=output, rtc_user=fake_rtc_user
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
    assert assistant_messages, "deberia haber un mensaje del agente persistido"
    assert assistant_messages[0]["citations"], "las citas deben estar persistidas"


@pytest.mark.asyncio
async def test_orchestrator_low_confidence_when_pipeline_has_no_citations(
    fake_rtc_user, fake_chunk_hits
) -> None:
    retrieved = [
        RetrievedChunk(
            chunk_id=h.chunk_id,
            document_id=h.document_id,
            document_title=h.document_title,
            country_iso=h.country_iso,
            chunk_index=h.chunk_index,
            content=h.content,
            similarity=h.similarity,
        )
        for h in fake_chunk_hits
    ]
    output = PipelineOutput(
        retrieved=retrieved,
        top_similarity=retrieved[0].similarity,
        answer=None,
        raw_answer_text=None,
        error="missing_citations",
    )

    orchestrator, conv = _build_orchestrator(
        pipeline_output=output, rtc_user=fake_rtc_user
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
    output = PipelineOutput(
        retrieved=[],
        top_similarity=0.0,
        answer=None,
        raw_answer_text=None,
    )
    rtc_users = {fake_rtc_user.phone_e164: fake_rtc_user}
    conv = FakeConversationRepository()
    wa = FakeWhatsAppClient()
    orchestrator = AgentOrchestrator(
        rtc_repository=FakeRtcRepository(rtc_users),  # type: ignore[arg-type]
        conversation_repository=conv,  # type: ignore[arg-type]
        system_prompt_repository=FakeSystemPromptRepository(
            FakeActivePrompt(version=1, content="System prompt v1.")
        ),  # type: ignore[arg-type]
        pipeline=_StaticPipeline(output),  # type: ignore[arg-type]
        whatsapp_client=wa,  # type: ignore[arg-type]
        similarity_threshold=0.75,
    )

    result = await orchestrator.handle_playground_message(
        rtc_user_id=fake_rtc_user.id,
        text_body="hola desde playground",
    )

    assert result.decision == "no_match"
    assert not wa.sent
