"""Tests unitarios de los nodos del grafo (spec 003).

No instancian Postgres: usan los fakes de `conftest.py` para verificar
la logica de routing condicional.
"""

from __future__ import annotations

import uuid

import pytest

from biomont_common.schemas.agent_graph import Intent, IntentClassification
from biomont_common.schemas.knowledge import DocumentKind, FaqHit
from biomont_common.schemas.products import ProductCandidate

from app.agent.graph.nodes.faq_retriever import FaqRetrieverNode
from app.agent.graph.nodes.hybrid_retriever import HybridRetrieverNode
from app.agent.graph.nodes.intent_classifier import (
    apply_intent_lexical_calibration,
)
from app.agent.graph.nodes.meta_filter import MetaFilterNode
from app.agent.graph.nodes.product_resolver import ProductResolverNode
from app.agent.graph.nodes.state_updater import StateUpdaterNode

from tests.conftest import (
    FakeConversationStateRepository,
    FakeEmbeddings,
    FakeFaqRepository,
    FakeHybridRagRepository,
    FakeProductRepository,
)


@pytest.mark.asyncio
async def test_product_resolver_resolves_top_with_high_confidence():
    product_id = uuid.uuid4()
    repo = FakeProductRepository(
        candidates=[
            ProductCandidate(
                product_id=product_id,
                product_name="Proteggo 3M",
                alias_matched="el verde",
                similarity=0.92,
            ),
            ProductCandidate(
                product_id=uuid.uuid4(),
                product_name="Proteggo M",
                alias_matched="proteggo",
                similarity=0.65,
            ),
        ]
    )
    node = ProductResolverNode(
        repository=repo, threshold=0.55, margin=0.10
    )
    state = {
        "query": "dosis del verde",
        "intent": Intent.dosage_question,
        "allowed_countries": ["PE"],
        "inherited_product_id": None,
        "trace": [],
    }

    updates = await node(state)
    assert updates["product_id"] == product_id
    assert updates["ambiguous_candidates"] == []


@pytest.mark.asyncio
async def test_product_resolver_marks_ambiguous_when_margin_low():
    repo = FakeProductRepository(
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
    node = ProductResolverNode(
        repository=repo, threshold=0.55, margin=0.10
    )
    state = {
        "query": "proteggo",
        "intent": Intent.dosage_question,
        "allowed_countries": [],
        "inherited_product_id": None,
        "trace": [],
    }
    updates = await node(state)
    assert updates["product_id"] is None
    assert len(updates["ambiguous_candidates"]) >= 2


@pytest.mark.asyncio
async def test_product_resolver_inherits_from_conversation_state():
    inherited = uuid.uuid4()

    class _ProductRow:
        def __init__(self, id_, name):
            self.id = id_
            self.name = name

    repo = FakeProductRepository(
        candidates=[],
        by_id={inherited: _ProductRow(inherited, "Proteggo 3M")},
    )
    node = ProductResolverNode(repository=repo)
    state = {
        "query": "y la dosis para sarna?",
        "intent": Intent.clinical_protocol,
        "allowed_countries": [],
        "inherited_product_id": inherited,
        "trace": [],
    }
    updates = await node(state)
    assert updates["product_id"] == inherited
    assert updates["product_inherited"] is True


@pytest.mark.asyncio
async def test_meta_filter_maps_intent_to_kinds():
    node = MetaFilterNode()
    cases = [
        (Intent.faq, [DocumentKind.balotario]),
        (Intent.clinical_protocol, [DocumentKind.bitacora]),
        (
            Intent.dosage_question,
            [DocumentKind.bitacora, DocumentKind.ficha_tecnica],
        ),
        (
            Intent.safety_question,
            [
                DocumentKind.ficha_tecnica,
                DocumentKind.bitacora,
                DocumentKind.balotario,
            ],
        ),
        (Intent.chitchat, None),
    ]
    for intent, expected in cases:
        state = {"intent": intent, "trace": []}
        updates = await node(state)
        assert updates["filter_kinds"] == expected, (intent, expected)


@pytest.mark.asyncio
async def test_meta_filter_full_corpus_uses_all_kinds_irrespective_of_intent():
    """RAG_FULL_CORPUS_FOR_ALL_INTENTS debe exponer todos los tipos chunk al hibrido."""

    node = MetaFilterNode(full_corpus_for_all_intents=True)
    expected_kinds = set(DocumentKind)
    for intent in (Intent.faq, Intent.dosage_question, Intent.chitchat):
        state = {"intent": intent, "trace": []}
        updates = await node(state)
        assert set(updates["filter_kinds"] or []) == expected_kinds, intent


@pytest.mark.asyncio
async def test_faq_retriever_full_corpus_runs_when_intent_is_not_faq_like():
    hit = FaqHit(
        faq_id=uuid.uuid4(),
        product_id=None,
        document_id=uuid.uuid4(),
        question="Q",
        answer="A",
        final_score=0.5,
    )
    repo = FakeFaqRepository(hits=[hit])
    embeddings = FakeEmbeddings()
    node = FaqRetrieverNode(
        repository=repo,
        embeddings=embeddings,
        vector_weight=0.7,
        bm25_weight=0.3,
        full_corpus_for_all_intents=True,
    )
    state = {"intent": Intent.dosage_question, "trace": [], "query": "x"}
    updates = await node(state)
    assert updates["faq_hits"] == [hit]


@pytest.mark.asyncio
async def test_faq_retriever_skips_when_intent_irrelevant():
    repo = FakeFaqRepository(hits=[])
    embeddings = FakeEmbeddings()
    node = FaqRetrieverNode(
        repository=repo,
        embeddings=embeddings,
        vector_weight=0.7,
        bm25_weight=0.3,
    )
    state = {"intent": Intent.dosage_question, "trace": [], "query": "x"}
    updates = await node(state)
    assert updates["faq_hits"] == []
    assert updates["faq_direct_answer"] is None


@pytest.mark.asyncio
async def test_hybrid_retriever_returns_repo_hits(fake_hybrid_chunks):
    repo = FakeHybridRagRepository(hits=fake_hybrid_chunks)
    embeddings = FakeEmbeddings()
    node = HybridRetrieverNode(
        repository=repo,
        embeddings=embeddings,
        vector_weight=0.7,
        bm25_weight=0.3,
        top_k=6,
        candidate_k=25,
    )
    state = {
        "query": "dosis sarna",
        "allowed_countries": ["PE"],
        "product_id": None,
        "filter_kinds": [DocumentKind.bitacora],
        "trace": [],
    }
    updates = await node(state)
    assert len(updates["retrieved"]) == len(fake_hybrid_chunks)
    assert updates["top_similarity"] == fake_hybrid_chunks[0].final_score
    assert repo.last_call is not None
    assert repo.last_call["kinds"] == [DocumentKind.bitacora]
    assert repo.last_call["allowed_countries"] == ["PE"]


@pytest.mark.asyncio
async def test_state_updater_persists_state():
    repo = FakeConversationStateRepository()
    node = StateUpdaterNode(repository=repo)
    conv = uuid.uuid4()
    prod = uuid.uuid4()
    state = {
        "conversation_id": conv,
        "product_id": prod,
        "intent": Intent.dosage_question,
        "trace": [],
    }
    updates = await node(state)
    assert updates["state_updated"] is True
    assert conv in repo.state_by_conv
    assert repo.state_by_conv[conv]["current_product_id"] == prod
    assert repo.state_by_conv[conv]["last_intent"] == "dosage_question"


def test_intent_calibration_moves_adversos_from_faq_to_safety() -> None:
    baseline = IntentClassification(intent=Intent.faq, confidence=0.9)
    calibrated = apply_intent_lexical_calibration(
        baseline, "Cuales son los efectos adversos del protego"
    )
    assert calibrated.intent == Intent.safety_question
    assert calibrated.confidence >= 0.88


def test_intent_calibration_keeps_gestacion_in_faq() -> None:
    baseline = IntentClassification(intent=Intent.safety_question, confidence=1.0)
    calibrated = apply_intent_lexical_calibration(
        baseline, "Puede usarse en gestacion?"
    )
    assert calibrated.intent == Intent.faq
