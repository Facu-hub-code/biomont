"""Tests unitarios de los nodos del grafo (spec 003/007)."""

from __future__ import annotations

import uuid

import pytest

from biomont_common.db.agent_config_repository import _LEGACY_INTENT_KINDS
from biomont_common.schemas.agent_graph import Intent, IntentClassification
from biomont_common.schemas.knowledge import DocumentKind
from biomont_common.schemas.products import ProductCandidate

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
        (Intent.clinical_protocol, [DocumentKind.bitacora, DocumentKind.balotario]),
        (
            Intent.dosage_question,
            [
                DocumentKind.bitacora,
                DocumentKind.ficha_tecnica,
                DocumentKind.balotario,
            ],
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
        state = {
            "intent": intent,
            "trace": [],
            "runtime_full_corpus": False,
            "intent_kinds_by_slug": _LEGACY_INTENT_KINDS,
        }
        updates = await node(state)
        assert updates["filter_kinds"] == expected, (intent, expected)


@pytest.mark.asyncio
async def test_meta_filter_full_corpus_uses_all_kinds_irrespective_of_intent():
    node = MetaFilterNode(full_corpus_for_all_intents=True)
    expected_kinds = set(DocumentKind)
    for intent in (Intent.dosage_question, Intent.safety_question, Intent.chitchat):
        state = {
            "intent": intent,
            "trace": [],
            "runtime_full_corpus": True,
            "intent_kinds_by_slug": {},
        }
        updates = await node(state)
        assert set(updates["filter_kinds"] or []) == expected_kinds, intent


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


def test_intent_calibration_moves_dosage_with_weight_to_dose_calc() -> None:
    baseline = IntentClassification(intent=Intent.dosage_question, confidence=0.9)
    calibrated = apply_intent_lexical_calibration(
        baseline, "perro de 25 kg que tableta de proteggo 3m"
    )
    assert calibrated.intent == Intent.dose_calculation


def test_intent_calibration_moves_adversos_from_dosage_to_safety() -> None:
    baseline = IntentClassification(intent=Intent.dosage_question, confidence=0.9)
