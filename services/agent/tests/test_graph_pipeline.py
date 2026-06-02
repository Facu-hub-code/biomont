"""Tests del grafo end-to-end (spec 003/007)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest

from biomont_common.schemas.agent_graph import Intent
from biomont_common.schemas.knowledge import DocumentKind
from biomont_common.schemas.products import ProductCandidate
from biomont_common.schemas.rag import RagAnswer

from biomont_common.settings import RagSettings
from app.agent.graph.graph import build_graph

from tests.conftest import (
    FakeAgentConfigRepository,
    FakeComparisonRepository,
    FakeConversationStateRepository,
    FakeDosingRepository,
    FakeEmbeddings,
    FakeHybridRagRepository,
    FakeProductRepository,
)


def _build_test_pipeline(**kwargs):
    defaults = dict(
        rag_repository=kwargs.pop("rag_repository"),
        product_repository=kwargs.pop("product_repository"),
        state_repository=kwargs.pop("state_repository"),
        dosing_repository=FakeDosingRepository(),
        comparison_repository=FakeComparisonRepository(),
        agent_config_repository=FakeAgentConfigRepository(),
        embeddings=FakeEmbeddings(),
    )
    defaults.update(kwargs)
    return build_graph(**defaults)


@dataclass
class _FakeIntent:
    intent: Intent
    confidence: float = 0.95


class _FakeStructuredOutput:
    def __init__(self, value):
        self._value = value

    async def ainvoke(self, _messages):
        return self._value


class _FakeChatModel:
    def __init__(self, *, intent: Intent, answer: RagAnswer):
        self._intent = intent
        self._answer = answer

    def with_structured_output(self, schema):
        name = getattr(schema, "__name__", "")
        if name == "IntentClassification":
            return _FakeStructuredOutput(_FakeIntent(intent=self._intent))
        if name == "RagAnswer":
            return _FakeStructuredOutput(self._answer)
        return _FakeStructuredOutput(self._answer)


@pytest.mark.asyncio
async def test_graph_safety_question_uses_hybrid_and_answerer(fake_hybrid_chunks):
    doc_id = fake_hybrid_chunks[0].document_id
    rag_repo = FakeHybridRagRepository(hits=fake_hybrid_chunks)
    product_repo = FakeProductRepository(candidates=[])
    state_repo = FakeConversationStateRepository()

    rag_answer = RagAnswer(
        answer="Consulte con el veterinario sobre uso en gestantes.",
        citations=[
            {
                "document_id": str(doc_id),
                "document_title": "Balotario Proteggo",
                "similarity": 0.88,
            }
        ],
    )

    pipeline = _build_test_pipeline(
        rag_repository=rag_repo,
        product_repository=product_repo,
        state_repository=state_repo,
        chat_model=_FakeChatModel(
            intent=Intent.safety_question,
            answer=rag_answer,
        ),
    )

    output = await pipeline.run(
        query="Puede usarse en gestacion?",
        allowed_countries=["PE"],
        system_prompt="Sos asistente",
        conversation_id=uuid.uuid4(),
    )

    assert output.answer_text == rag_answer.answer
    assert output.retrieved == fake_hybrid_chunks
    nodes_visited = {t.node for t in output.graph_trace}
    assert "HybridRetriever" in nodes_visited
    assert "Answerer" in nodes_visited
    assert "FAQRetriever" not in nodes_visited


@pytest.mark.asyncio
async def test_graph_full_path_dosage_question(fake_hybrid_chunks):
    product_id = uuid.uuid4()
    doc_id = fake_hybrid_chunks[0].document_id
    product_repo = FakeProductRepository(
        candidates=[
            ProductCandidate(
                product_id=product_id,
                product_name="Proteggo 3M",
                alias_matched="proteggo 3m",
                similarity=0.95,
            )
        ]
    )
    rag_repo = FakeHybridRagRepository(hits=fake_hybrid_chunks)
    state_repo = FakeConversationStateRepository()

    rag_answer = RagAnswer(
        answer="Dosis: 25-56 mg/kg.",
        citations=[
            {
                "document_id": str(doc_id),
                "document_title": "Bitacora Proteggo 3M",
                "similarity": 0.88,
            }
        ],
    )

    pipeline = _build_test_pipeline(
        rag_repository=rag_repo,
        product_repository=product_repo,
        state_repository=state_repo,
        chat_model=_FakeChatModel(
            intent=Intent.dosage_question, answer=rag_answer
        ),
    )

    output = await pipeline.run(
        query="dosis del proteggo 3m?",
        allowed_countries=["PE"],
        system_prompt="Sos asistente",
        conversation_id=uuid.uuid4(),
    )

    assert output.product_id == product_id
    assert output.intent == Intent.dosage_question
    assert output.answer_text == "Dosis: 25-56 mg/kg."
    assert rag_repo.last_call is not None
    assert rag_repo.last_call["product_id"] == product_id
    assert rag_repo.last_call["kinds"]
    assert DocumentKind.bitacora in rag_repo.last_call["kinds"]
    assert DocumentKind.balotario in rag_repo.last_call["kinds"]


@pytest.mark.asyncio
async def test_graph_dosage_includes_balotario_when_full_corpus_flag(
    fake_hybrid_chunks,
):
    product_id = uuid.uuid4()
    product_repo = FakeProductRepository(
        candidates=[
            ProductCandidate(
                product_id=product_id,
                product_name="Proteggo 3M",
                alias_matched="proteggo 3m",
                similarity=0.95,
            )
        ]
    )
    rag_repo = FakeHybridRagRepository(hits=fake_hybrid_chunks)
    state_repo = FakeConversationStateRepository()
    rag_answer = RagAnswer(
        answer="x",
        citations=[
            {
                "document_id": str(fake_hybrid_chunks[0].document_id),
                "document_title": "x",
                "similarity": 0.88,
            }
        ],
    )
    cfg = RagSettings(full_corpus_for_all_intents=True)
    pipeline = _build_test_pipeline(
        rag_repository=rag_repo,
        product_repository=product_repo,
        state_repository=state_repo,
        settings=cfg,
        chat_model=_FakeChatModel(
            intent=Intent.dosage_question, answer=rag_answer
        ),
    )
    await pipeline.run(
        query="dosis del proteggo 3m?",
        allowed_countries=["PE"],
        system_prompt="Sos asistente",
        conversation_id=uuid.uuid4(),
    )
    kinds = rag_repo.last_call["kinds"] if rag_repo.last_call else []
    assert DocumentKind.balotario in kinds


@pytest.mark.asyncio
async def test_graph_ambiguous_product_short_circuits():
    product_repo = FakeProductRepository(
        candidates=[
            ProductCandidate(
                product_id=uuid.uuid4(),
                product_name="Proteggo M",
                alias_matched="proteggo",
                similarity=0.60,
            ),
            ProductCandidate(
                product_id=uuid.uuid4(),
                product_name="Proteggo 3M",
                alias_matched="proteggo 3m",
                similarity=0.58,
            ),
        ]
    )
    rag_repo = FakeHybridRagRepository(hits=[])
    state_repo = FakeConversationStateRepository()

    pipeline = _build_test_pipeline(
        rag_repository=rag_repo,
        product_repository=product_repo,
        state_repository=state_repo,
        chat_model=_FakeChatModel(
            intent=Intent.dosage_question,
            answer=RagAnswer(
                answer="x",
                citations=[
                    {
                        "document_id": str(uuid.uuid4()),
                        "document_title": "x",
                        "similarity": 0.1,
                    }
                ],
            ),
        ),
    )

    output = await pipeline.run(
        query="proteggo dosis?",
        allowed_countries=[],
        system_prompt="x",
        conversation_id=uuid.uuid4(),
    )

    assert output.ambiguous_candidates
    assert output.answer_text is None
    nodes = {t.node for t in output.graph_trace}
    assert "ProductResolver" in nodes
    assert "HybridRetriever" not in nodes
    assert "Answerer" not in nodes
