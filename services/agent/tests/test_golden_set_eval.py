"""Evaluacion contra el golden set (spec 003, CA-15)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

from biomont_common.schemas.agent_graph import Intent  # noqa: E402
from biomont_common.schemas.knowledge import DocumentKind, HybridChunkHit  # noqa: E402
from biomont_common.schemas.products import ProductCandidate  # noqa: E402
from biomont_common.schemas.rag import RagAnswer  # noqa: E402

from app.agent.graph.graph import build_graph  # noqa: E402

from tests.conftest import (  # noqa: E402
    FakeAgentConfigRepository,
    FakeComparisonRepository,
    FakeConversationStateRepository,
    FakeDosingRepository,
    FakeEmbeddings,
    FakeHybridRagRepository,
    FakeProductRepository,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GOLDEN_PATH = _REPO_ROOT / "evaluation" / "golden_set.yaml"
_BASELINE_PATH = _REPO_ROOT / "evaluation" / "baseline.json"
_MAX_REGRESSION = 0.05


class _ProductRow:
    def __init__(self, id_: uuid.UUID, name: str) -> None:
        self.id = id_
        self.name = name


class _ScriptedChat:
    def __init__(self, *, intent: Intent, answer: RagAnswer) -> None:
        self._intent = intent
        self._answer = answer

    def with_structured_output(self, schema):
        name = getattr(schema, "__name__", "")

        class _Out:
            def __init__(self, value):
                self._value = value

            async def ainvoke(self, _msgs):
                return self._value

        class _IntentLike:
            def __init__(self, intent: Intent) -> None:
                self.intent = intent
                self.confidence = 0.99

        if name == "IntentClassification":
            return _Out(_IntentLike(self._intent))
        return _Out(self._answer)


def _load_cases() -> list[dict]:
    if not _GOLDEN_PATH.exists():
        pytest.skip(f"golden set no encontrado en {_GOLDEN_PATH}")
    with _GOLDEN_PATH.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return list(data.get("cases") or [])


def _load_baseline() -> dict:
    if not _BASELINE_PATH.exists():
        return {"accuracy": 0.0}
    with _BASELINE_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _build_fakes_for(case: dict):
    expected_intent = Intent(case["expected_intent"])
    expected_product = case.get("expected_product")
    decision = case["expected_decision"]

    if expected_intent == Intent.dosage_question and not expected_product:
        candidates = [
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
    elif expected_product:
        candidates = [
            ProductCandidate(
                product_id=uuid.uuid4(),
                product_name=expected_product,
                alias_matched=expected_product.lower(),
                similarity=0.95,
            )
        ]
    else:
        candidates = []

    product_repo = FakeProductRepository(candidates=candidates)
    rag_hits: list[HybridChunkHit] = []
    if decision == "answered":
        rag_hits = [
            HybridChunkHit(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                document_title=f"Bitacora {expected_product or 'X'}",
                product_id=candidates[0].product_id if candidates else None,
                kind=DocumentKind.bitacora,
                chunk_index=0,
                section_type="protocol",
                content="Protocolo: 10 mg/kg c/12 semanas. Util en DAPP. Seguro en gestantes.",
                country_iso="PE",
                vector_score=0.9,
                bm25_score=0.8,
                final_score=0.88,
            )
        ]

    rag_repo = FakeHybridRagRepository(hits=rag_hits)
    state_repo = FakeConversationStateRepository()

    answer = RagAnswer(
        answer="Protocolo: 10 mg/kg c/12 semanas. Aplicable a DAPP y gestantes.",
        citations=[
            {
                "document_id": str(rag_hits[0].document_id)
                if rag_hits
                else str(uuid.uuid4()),
                "document_title": "Bitacora",
                "similarity": 0.88,
            }
        ],
    )
    chat = _ScriptedChat(intent=expected_intent, answer=answer)

    return product_repo, rag_repo, state_repo, chat


def _matches_kinds(observed, expected) -> bool:
    if expected is None:
        return observed is None
    if observed is None:
        return False
    observed_values = sorted(
        k.value if isinstance(k, DocumentKind) else str(k) for k in observed
    )
    return observed_values == sorted(expected)


@pytest.mark.eval
@pytest.mark.asyncio
async def test_golden_set_accuracy():
    cases = _load_cases()
    if not cases:
        pytest.skip("golden set vacio")

    intent_match = 0
    decision_match = 0
    product_match = 0
    kinds_match = 0
    substring_match = 0
    answered_total = 0

    for case in cases:
        product_repo, rag_repo, state_repo, chat = _build_fakes_for(case)
        pipeline = build_graph(
            rag_repository=rag_repo,
            product_repository=product_repo,
            dosing_repository=FakeDosingRepository(),
            comparison_repository=FakeComparisonRepository(),
            state_repository=state_repo,
            agent_config_repository=FakeAgentConfigRepository(),
            embeddings=FakeEmbeddings(),
            chat_model=chat,
        )
        output = await pipeline.run(
            query=case["query"],
            allowed_countries=case.get("allowed_countries") or [],
            system_prompt="eval",
            conversation_id=uuid.uuid4(),
        )

        if output.intent and output.intent.value == case["expected_intent"]:
            intent_match += 1

        expected_product = case.get("expected_product")
        if expected_product is None:
            if output.product_id is None:
                product_match += 1
        else:
            if output.product_id is not None:
                product_match += 1

        if _matches_kinds(
            _kinds_from_trace(output.graph_trace),
            case.get("expected_kind_in_filter"),
        ):
            kinds_match += 1

        observed_decision = _decision_from_output(output)
        if observed_decision == case["expected_decision"]:
            decision_match += 1

        if case["expected_decision"] == "answered":
            answered_total += 1
            text = (output.answer_text or "").lower()
            substrings = [s.lower() for s in case.get("expected_substrings") or []]
            if substrings and all(s in text for s in substrings):
                substring_match += 1
            elif not substrings:
                substring_match += 1

    total = len(cases)
    accuracy = decision_match / total if total else 0.0
    summary = {
        "total": total,
        "accuracy": accuracy,
        "intent_match_rate": intent_match / total if total else 0.0,
        "product_match_rate": product_match / total if total else 0.0,
        "kinds_match_rate": kinds_match / total if total else 0.0,
        "answered_substring_match_rate": (
            substring_match / answered_total if answered_total else 1.0
        ),
    }
    print(f"\n[eval] golden_set summary={json.dumps(summary, indent=2)}")

    baseline = _load_baseline()
    baseline_acc = float(baseline.get("accuracy") or 0.0)
    assert accuracy + _MAX_REGRESSION >= baseline_acc, (
        f"regresion bloqueante: accuracy={accuracy:.3f} < "
        f"baseline={baseline_acc:.3f} - {_MAX_REGRESSION:.3f}"
    )


def _decision_from_output(output) -> str:
    if output.ambiguous_candidates:
        return "low_confidence"
    if getattr(output, "structured_response", False) and output.answer_text:
        return "answered"
    if output.answer_text and output.citations:
        return "answered"
    if not output.retrieved:
        return "no_match"
    return "low_confidence"


def _kinds_from_trace(trace) -> list[str] | None:
    for entry in trace:
        if entry.node == "MetaFilter" and entry.payload:
            kinds = entry.payload.get("kinds")
            return kinds
    return None
