"""Caso de uso principal del agente.

Orquesta lookup del RTC, ejecucion del grafo LangGraph, decision de
respuesta y persistencia de mensajes/decisiones/tickets.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from biomont_common.db.conversation_repository import ConversationRepository
from biomont_common.db.conversation_state_repository import (
    ConversationStateRepository,
)
from biomont_common.db.rtc_repository import RtcRepository, RtcUser
from biomont_common.db.system_prompt_repository import SystemPromptRepository
from biomont_common.logging import get_logger
from biomont_common.whatsapp_format import normalize_whatsapp_markdown
from biomont_common.schemas.rag import Citation, RagAnswer, RetrievedChunk

from app.agent.graph.graph import GraphOutput, GraphPipeline
from app.integrations.whatsapp_client import WhatsAppClient

_logger = get_logger("agent.orchestrator")

Channel = Literal["whatsapp", "playground"]
DecisionKind = Literal[
    "answered", "low_confidence", "no_match", "blocked", "error"
]


@dataclass(slots=True)
class PipelineOutput:
    retrieved: list[RetrievedChunk]
    top_similarity: float
    answer: RagAnswer | None
    raw_answer_text: str | None
    error: str | None = None


def maybe_product_confirmation_reply(
    *,
    decision: DecisionKind,
    graph_output: GraphOutput | None,
) -> str | None:
    if decision != "answered" or graph_output is None:
        return None
    product_id = graph_output.product_id
    label = (graph_output.product_name or "").strip()
    if product_id is None or not label:
        return None
    if graph_output.product_inherited:
        return (
            f"Para esta respuesta sigo usando la informacion del producto "
            f"*{label}*."
        )
    return (
        f"Para esta respuesta tome como referencia el producto *{label}*."
    )


_AMBIGUOUS_PRODUCT_TEMPLATE = (
    "Para responder bien necesito que me confirmes el producto. "
    "Estoy entre: {options}. ¿Cual te interesa?"
)


class PlaygroundRtcForbiddenError(Exception):
    """RTC inexistente o inhabilitado; el playground no debe persistir ni enviar WhatsApp."""


@dataclass(slots=True)
class HandleResult:
    decision: DecisionKind
    reply_text: str
    ticket_id: str | None = None


_NOT_AUTHORIZED_MESSAGE = (
    "No estas autorizado para usar este canal. Si crees que es un error, "
    "contacta al equipo de Biomont."
)


def effective_retrieval_similarity_threshold(
    *,
    configured_threshold: float,
    rag_vector_weight: float | None,
) -> float:
    """Umbral efectivo vs score fusionado vec+BM25 del grafo."""

    if rag_vector_weight is not None and rag_vector_weight > 0:
        return min(float(configured_threshold), float(rag_vector_weight))
    return float(configured_threshold)


_NO_INFO_MESSAGE_TEMPLATE = (
    "No tengo esa informacion en mis documentos validados.\n"
    "Cree el ticket #{ticket_id} para que el equipo lo revise."
)


_LOW_CONFIDENCE_MESSAGE = (
    "No tengo informacion con suficiente confianza. Cree un ticket para "
    "que el equipo lo revise (#{ticket_id})."
)


class AgentOrchestrator:
    def __init__(
        self,
        *,
        rtc_repository: RtcRepository,
        conversation_repository: ConversationRepository,
        system_prompt_repository: SystemPromptRepository,
        pipeline: GraphPipeline,
        whatsapp_client: WhatsAppClient,
        similarity_threshold: float,
        conversation_state_repository: ConversationStateRepository | None = None,
        rag_vector_weight: float | None = None,
    ) -> None:
        self._rtc = rtc_repository
        self._conversations = conversation_repository
        self._prompts = system_prompt_repository
        self._pipeline = pipeline
        self._whatsapp = whatsapp_client
        self._threshold = similarity_threshold
        self._state_repo = conversation_state_repository
        self._rag_vector_weight = rag_vector_weight

    async def handle_incoming_message(
        self,
        *,
        from_phone_e164: str,
        text_body: str,
    ) -> HandleResult:
        rtc = await self._rtc.find_by_phone(from_phone_e164)

        if rtc is None or not rtc.enabled:
            await self._send(from_phone_e164, _NOT_AUTHORIZED_MESSAGE)
            await self._conversations.insert_decision(
                message_id=None,
                decision="blocked",
                reasoning="phone_not_authorized",
                retrieved=[],
                top_similarity=None,
                system_prompt_version=None,
            )
            _logger.info(
                "agent_blocked",
                action="blocked",
                channel="whatsapp",
                phone_hash=_hash_phone(from_phone_e164),
            )
            return HandleResult(
                decision="blocked",
                reply_text=_NOT_AUTHORIZED_MESSAGE,
            )

        return await self._run_pipeline_for_rtc(
            rtc=rtc,
            text_body=text_body,
            channel="whatsapp",
            deliver_whatsapp=True,
        )

    async def handle_playground_message(
        self,
        *,
        rtc_user_id: UUID,
        text_body: str,
    ) -> HandleResult:
        _logger.info(
            "playground_message",
            action="playground_inbound",
            channel="playground",
            rtc_user_id=str(rtc_user_id),
        )
        rtc = await self._rtc.find_by_id(rtc_user_id)
        if rtc is None or not rtc.enabled:
            raise PlaygroundRtcForbiddenError()
        return await self._run_pipeline_for_rtc(
            rtc=rtc,
            text_body=text_body,
            channel="playground",
            deliver_whatsapp=False,
        )

    async def _run_pipeline_for_rtc(
        self,
        *,
        rtc: RtcUser,
        text_body: str,
        channel: Channel,
        deliver_whatsapp: bool,
    ) -> HandleResult:
        started = time.perf_counter()
        conversation_id = (
            await self._conversations.get_or_create_active_conversation(rtc.id)
        )

        user_message_id = await self._conversations.insert_message(
            conversation_id=conversation_id,
            role="user",
            content=text_body,
        )

        active_prompt = await self._prompts.get_active()
        system_prompt = (
            active_prompt.content
            if active_prompt is not None
            else "Eres el asistente de productos veterinarios de Biomont."
        )
        prompt_version = active_prompt.version if active_prompt else None

        inherited_product_id = await self._read_inherited_product(conversation_id)
        graph_output = await self._pipeline.run(
            query=text_body,
            allowed_countries=rtc.countries,
            system_prompt=system_prompt,
            conversation_id=conversation_id,
            inherited_product_id=inherited_product_id,
        )
        output = _graph_output_to_pipeline_output(graph_output)
        ambiguous = list(graph_output.ambiguous_candidates)
        graph_trace = [t.model_dump(mode="json") for t in graph_output.graph_trace]

        elapsed_ms = int((time.perf_counter() - started) * 1000)

        if graph_output.structured_response and graph_output.answer_text:
            decision: DecisionKind = "answered"
            reply_text = graph_output.answer_text
            answer = None
            ticket_id = None
        else:
            decision, reply_text, answer, ticket_id = await self._decide(
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                output=output,
                text_body=text_body,
                ambiguous_candidates=ambiguous,
            )

        confirmation = maybe_product_confirmation_reply(
            decision=decision,
            graph_output=graph_output,
        )

        if confirmation:
            await self._conversations.insert_message(
                conversation_id=conversation_id,
                role="assistant",
                content=confirmation,
                citations=[],
                latency_ms=None,
            )

        assistant_message_id = await self._conversations.insert_message(
            conversation_id=conversation_id,
            role="assistant",
            content=reply_text,
            citations=[c.model_dump(mode="json") for c in (answer.citations if answer else [])],
            latency_ms=elapsed_ms,
        )

        await self._conversations.insert_decision(
            message_id=assistant_message_id,
            decision=decision,
            reasoning=output.error,
            retrieved=[
                {
                    "document_id": str(chunk.document_id),
                    "chunk_id": str(chunk.chunk_id),
                    "similarity": chunk.similarity,
                }
                for chunk in output.retrieved
            ],
            top_similarity=output.top_similarity or None,
            system_prompt_version=prompt_version,
            graph_trace=graph_trace,
        )

        combined_reply_for_client = (
            f"{confirmation}\n\n{reply_text}" if confirmation else reply_text
        )

        if deliver_whatsapp:
            if confirmation:
                await self._send(rtc.phone_e164, confirmation)
            await self._send(rtc.phone_e164, reply_text)

        _logger.info(
            "agent_decision",
            action="decision",
            channel=channel,
            decision=decision,
            top_similarity=output.top_similarity,
            chunks=len(output.retrieved),
            latency_ms=elapsed_ms,
            ticket_id=ticket_id,
            conversation_id=str(conversation_id),
            rtc_user_id=str(rtc.id),
            pipeline="graph",
        )
        return HandleResult(
            decision=decision,
            reply_text=combined_reply_for_client,
            ticket_id=ticket_id,
        )

    async def _read_inherited_product(self, conversation_id: UUID) -> UUID | None:
        if self._state_repo is None:
            return None
        record = await self._state_repo.get(conversation_id)
        return record.current_product_id if record else None

    async def _decide(
        self,
        *,
        conversation_id,
        user_message_id,
        output: PipelineOutput,
        text_body: str,
        ambiguous_candidates: list[Any] | None = None,
    ) -> tuple[DecisionKind, str, RagAnswer | None, str | None]:
        if ambiguous_candidates:
            names = " / ".join(c.product_name for c in ambiguous_candidates[:3])
            return (
                "low_confidence",
                _AMBIGUOUS_PRODUCT_TEMPLATE.format(options=names),
                None,
                None,
            )

        gate = effective_retrieval_similarity_threshold(
            configured_threshold=self._threshold,
            rag_vector_weight=self._rag_vector_weight,
        )

        epsilon = 1e-5
        weak_retrieval = (
            not output.retrieved
            or output.top_similarity < gate - epsilon
        )

        if weak_retrieval:
            ticket_id = await self._conversations.insert_ticket(
                conversation_id=conversation_id,
                message_id=user_message_id,
                ticket_type="no_info",
                summary=text_body[:200],
                notes=(
                    f"top_similarity={output.top_similarity:.3f} "
                    f"gate={gate:.3f} "
                    f"chunks={len(output.retrieved)}"
                ),
            )
            return (
                "no_match",
                _NO_INFO_MESSAGE_TEMPLATE.format(ticket_id=str(ticket_id)[:8]),
                None,
                str(ticket_id),
            )

        if output.answer is None or not output.answer.citations:
            ticket_id = await self._conversations.insert_ticket(
                conversation_id=conversation_id,
                message_id=user_message_id,
                ticket_type="low_confidence",
                summary=text_body[:200],
                notes=output.error or "missing_citations",
            )
            return (
                "low_confidence",
                _LOW_CONFIDENCE_MESSAGE.format(ticket_id=str(ticket_id)[:8]),
                None,
                str(ticket_id),
            )

        rendered = _render_answer(output.answer)
        return ("answered", rendered, output.answer, None)

    async def _send(self, to: str, body: str) -> None:
        try:
            await self._whatsapp.send_text(
                to_phone_e164=to,
                body=normalize_whatsapp_markdown(body),
            )
        except Exception:
            _logger.exception(
                "agent_whatsapp_send_failed", action="send_failed"
            )


def _graph_output_to_pipeline_output(graph_output: GraphOutput) -> PipelineOutput:
    retrieved: list[RetrievedChunk] = [
        RetrievedChunk(
            chunk_id=hit.chunk_id,
            document_id=hit.document_id,
            document_title=hit.document_title,
            country_iso=hit.country_iso,
            chunk_index=hit.chunk_index,
            content=hit.content,
            similarity=hit.final_score,
        )
        for hit in graph_output.retrieved
    ]

    answer = None
    if graph_output.answer_text and graph_output.citations:
        answer = RagAnswer(
            answer=graph_output.answer_text,
            citations=[Citation(**c) for c in graph_output.citations],
        )
    return PipelineOutput(
        retrieved=retrieved,
        top_similarity=graph_output.top_similarity,
        answer=answer,
        raw_answer_text=answer.answer if answer else None,
        error=graph_output.error,
    )


def _render_answer(answer: RagAnswer) -> str:
    citations_block = "\n".join(f"- {c.document_title}" for c in answer.citations)
    return f"{answer.answer}\n\nFuentes:\n{citations_block}"


def _hash_phone(phone: str) -> str:
    import hashlib

    return hashlib.sha256(phone.encode("utf-8")).hexdigest()[:12]
