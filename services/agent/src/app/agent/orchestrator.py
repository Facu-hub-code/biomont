"""Caso de uso principal del agente.

Orquesta:
1. Lookup del RTC en `rtc_users`.
2. Gate de autorizacion + envio del mensaje "no autorizado" si falla.
3. Recupera el system prompt activo.
4. Ejecuta el pipeline (LCEL clasico o grafo LangGraph segun flag spec 003).
5. Decide answered / low_confidence / no_match / ambiguous_product.
6. Persiste mensajes + decision (con graph_trace si aplica) + ticket.
7. Envia la respuesta por WhatsApp (opcional en playground).

Disenado para ser facil de testear: las dependencias se inyectan y todas
las llamadas externas estan abstraidas.
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
from biomont_common.schemas.rag import Citation, RagAnswer

from app.agent.graph.graph import GraphOutput, GraphPipeline
from app.agent.rag_pipeline import PipelineOutput, RagPipeline
from app.integrations.whatsapp_client import WhatsAppClient

_logger = get_logger("agent.orchestrator")

Channel = Literal["whatsapp", "playground"]
DecisionKind = Literal[
    "answered", "low_confidence", "no_match", "blocked", "error"
]

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
        pipeline: "RagPipeline | GraphPipeline",
        whatsapp_client: WhatsAppClient,
        similarity_threshold: float,
        conversation_state_repository: ConversationStateRepository | None = None,
    ) -> None:
        self._rtc = rtc_repository
        self._conversations = conversation_repository
        self._prompts = system_prompt_repository
        self._pipeline = pipeline
        self._whatsapp = whatsapp_client
        self._threshold = similarity_threshold
        self._state_repo = conversation_state_repository
        self._use_graph = isinstance(pipeline, GraphPipeline)

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

        if self._use_graph:
            inherited_product_id = await self._read_inherited_product(
                conversation_id
            )
            graph_output: GraphOutput = await self._pipeline.run(  # type: ignore[union-attr]
                query=text_body,
                allowed_countries=rtc.countries,
                system_prompt=system_prompt,
                conversation_id=conversation_id,
                inherited_product_id=inherited_product_id,
            )
            adapter = _GraphPipelineAdapter(graph_output)
            output: PipelineOutput = adapter.to_pipeline_output()
            ambiguous = list(graph_output.ambiguous_candidates)
            graph_trace = [t.model_dump(mode="json") for t in graph_output.graph_trace]
        else:
            output = await self._pipeline.run(  # type: ignore[union-attr]
                query=text_body,
                allowed_countries=rtc.countries,
                system_prompt=system_prompt,
            )
            ambiguous = []
            graph_trace = []

        elapsed_ms = int((time.perf_counter() - started) * 1000)

        decision, reply_text, answer, ticket_id = await self._decide(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            output=output,
            text_body=text_body,
            ambiguous_candidates=ambiguous,
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

        if deliver_whatsapp:
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
            pipeline="graph" if self._use_graph else "lcel",
        )
        return HandleResult(
            decision=decision,
            reply_text=reply_text,
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
        # Ambiguedad de producto: respondemos pidiendo aclaracion sin abrir
        # ticket (no es un fallo, es una falta de informacion del usuario).
        if ambiguous_candidates:
            names = " / ".join(c.product_name for c in ambiguous_candidates[:3])
            return (
                "low_confidence",
                _AMBIGUOUS_PRODUCT_TEMPLATE.format(options=names),
                None,
                None,
            )

        if not output.retrieved or output.top_similarity < self._threshold:
            ticket_id = await self._conversations.insert_ticket(
                conversation_id=conversation_id,
                message_id=user_message_id,
                ticket_type="no_info",
                summary=text_body[:200],
                notes=(
                    f"top_similarity={output.top_similarity:.3f} "
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
            await self._whatsapp.send_text(to_phone_e164=to, body=body)
        except Exception:
            _logger.exception(
                "agent_whatsapp_send_failed", action="send_failed"
            )


def _render_answer(answer: RagAnswer) -> str:
    citations_block = "\n".join(
        f"- {c.document_title} (similitud {c.similarity * 100:.0f}%)"
        for c in answer.citations
    )
    return f"{answer.answer}\n\nFuentes:\n{citations_block}"


def _hash_phone(phone: str) -> str:
    import hashlib

    return hashlib.sha256(phone.encode("utf-8")).hexdigest()[:12]


@dataclass(slots=True)
class _GraphPipelineAdapter:
    """Adapta `GraphOutput` -> `PipelineOutput` para el resto del orchestrator.

    El grafo y el pipeline LCEL devuelven estructuras distintas; el adapter
    asegura que `_decide`/persistencia siguen recibiendo un objeto unico.
    """

    graph_output: GraphOutput

    def to_pipeline_output(self) -> PipelineOutput:
        from biomont_common.schemas.rag import RetrievedChunk

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
            for hit in self.graph_output.retrieved
        ]

        if (
            self.graph_output.faq_direct_answer is not None
            and self.graph_output.faq_hits
        ):
            top_faq = self.graph_output.faq_hits[0]
            faq_citations = [
                Citation(
                    document_id=top_faq.document_id,
                    document_title="FAQ",
                    similarity=top_faq.final_score,
                )
            ]
            answer = RagAnswer(
                answer=self.graph_output.faq_direct_answer,
                citations=faq_citations,
            )
            return PipelineOutput(
                retrieved=retrieved,
                top_similarity=top_faq.final_score,
                answer=answer,
                raw_answer_text=answer.answer,
                error=None,
            )

        answer = None
        if self.graph_output.answer_text and self.graph_output.citations:
            answer = RagAnswer(
                answer=self.graph_output.answer_text,
                citations=[
                    Citation(**c) for c in self.graph_output.citations
                ],
            )
        return PipelineOutput(
            retrieved=retrieved,
            top_similarity=self.graph_output.top_similarity,
            answer=answer,
            raw_answer_text=answer.answer if answer else None,
            error=self.graph_output.error,
        )
