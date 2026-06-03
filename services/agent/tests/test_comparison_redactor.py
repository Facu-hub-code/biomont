"""Tests del flujo comparacion + redactor (spec 013)."""

from __future__ import annotations

import uuid

import pytest

from biomont_common.schemas.agent_graph import Intent
from biomont_common.schemas.comparison import (
    ComparisonDiffItem,
    ComparisonDiffResult,
    ComparisonRedactorBullet,
    ComparisonRedactorOutput,
)
from biomont_common.schemas.products import ProductCandidate
from biomont_common.settings import RagSettings

from app.agent.graph.graph import build_graph

from tests.conftest import (
    FakeAgentConfigRepository,
    FakeConversationStateRepository,
    FakeDosingRepository,
    FakeEmbeddings,
    FakeHybridRagRepository,
    FakeProductRepository,
)


class _FakeIntent:
    def __init__(self, intent: Intent, confidence: float = 0.95):
        self.intent = intent
        self.confidence = confidence


class _FakeStructuredOutput:
    def __init__(self, value):
        self._value = value

    async def ainvoke(self, _messages):
        return self._value


class _FakeChatComparison:
    def __init__(self):
        self._intent = Intent.comparison_with_competitor
        self._redactor_out = ComparisonRedactorOutput(
            opening="Comparacion entre MARVO 20 y MARBOXI.",
            bullets=[
                ComparisonRedactorBullet(
                    column_key="dosis",
                    text=(
                        "MARVO 20: 1 tableta/10 kg. "
                        "MARBOXI: 2.75 a 5.5 mg/kg."
                    ),
                ),
                ComparisonRedactorBullet(
                    column_key="formula",
                    text=(
                        "MARVO 20: 20 mg marbofloxacina por tableta. "
                        "MARBOXI: presentaciones 25/50/100 mg."
                    ),
                ),
            ],
            closing_hint="Hay 2 diferencias mas en el cuadro.",
            footer="Fuente: comparativa comercial Biomont (v1).",
        )

    def with_structured_output(self, schema):
        name = getattr(schema, "__name__", "")
        if name == "IntentClassification":
            return _FakeStructuredOutput(_FakeIntent(self._intent))
        if name == "ComparisonRedactorOutput":
            return _FakeStructuredOutput(self._redactor_out)
        return _FakeStructuredOutput(self._redactor_out)


class _ComparisonRepoWithDiff:
    def __init__(self, product_id: uuid.UUID):
        self._product_id = product_id

    async def find_competitor_by_query(self, query: str, limit: int = 5):
        from biomont_common.schemas.comparison import Competitor

        return [
            Competitor(
                id=uuid.uuid4(),
                name="MARBOXI-TABS 25",
                brand=None,
                is_internal=False,
            )
        ]

    async def get_published_set(self, subject_product_id: uuid.UUID):
        if subject_product_id != self._product_id:
            return None
        return {
            "id": uuid.uuid4(),
            "subject_product_id": subject_product_id,
            "completeness_status": "complete",
            "published_version": 1,
        }

    async def diff_rows(self, **kwargs):
        return ComparisonDiffResult(
            subject_product_id=kwargs["subject_product_id"],
            subject_name="MARVO 20",
            competitor_name="MARBOXI-TABS 25",
            published_version=1,
            differences=[
                ComparisonDiffItem(
                    column_key="dosis",
                    header_label="DOSIS",
                    subject_value="1 tableta cada 10 kg",
                    competitor_value="2.75 a 5.5 mg/kg",
                    sort_order=9,
                ),
                ComparisonDiffItem(
                    column_key="formula",
                    header_label="FÓRMULA",
                    subject_value="20 mg marbofloxacina",
                    competitor_value="25 mg marbofloxacina",
                    sort_order=4,
                ),
            ],
        )


@pytest.mark.asyncio
async def test_graph_comparison_runs_redactor_node():
    product_id = uuid.uuid4()
    product_repo = FakeProductRepository(
        candidates=[
            ProductCandidate(
                product_id=product_id,
                product_name="Marvo 20",
                alias_matched="marvo 20",
                similarity=0.95,
            ),
        ]
    )
    pipeline = build_graph(
        rag_repository=FakeHybridRagRepository(hits=[]),
        product_repository=product_repo,
        state_repository=FakeConversationStateRepository(),
        dosing_repository=FakeDosingRepository(),
        comparison_repository=_ComparisonRepoWithDiff(product_id),
        agent_config_repository=FakeAgentConfigRepository(),
        embeddings=FakeEmbeddings(),
        chat_model=_FakeChatComparison(),
        settings=RagSettings(comparison_llm_redactor=True),
    )
    output = await pipeline.run(
        query="MARVO 20 versus Marboxi diferencias",
        allowed_countries=["PE"],
        system_prompt="Sos asistente",
        conversation_id=uuid.uuid4(),
    )
    nodes = {t.node for t in output.graph_trace}
    assert "CommercialComparisonDiff" in nodes
    assert "ComparisonRedactor" in nodes
    assert "Answerer" not in nodes
    assert output.answer_text
    assert "dosis" in output.answer_text.lower() or "DOSIS" in output.answer_text
    assert "comparativa comercial" in output.answer_text.lower()


@pytest.mark.asyncio
async def test_graph_comparison_flag_off_uses_deterministic_brief():
    product_id = uuid.uuid4()
    product_repo = FakeProductRepository(
        candidates=[
            ProductCandidate(
                product_id=product_id,
                product_name="Marvo 20",
                alias_matched="marvo",
                similarity=0.95,
            ),
        ]
    )
    pipeline = build_graph(
        rag_repository=FakeHybridRagRepository(hits=[]),
        product_repository=product_repo,
        state_repository=FakeConversationStateRepository(),
        dosing_repository=FakeDosingRepository(),
        comparison_repository=_ComparisonRepoWithDiff(product_id),
        agent_config_repository=FakeAgentConfigRepository(),
        embeddings=FakeEmbeddings(),
        chat_model=_FakeChatComparison(),
        settings=RagSettings(comparison_llm_redactor=False),
    )
    output = await pipeline.run(
        query="MARVO 20 vs Marboxi",
        allowed_countries=["PE"],
        system_prompt="Sos asistente",
        conversation_id=uuid.uuid4(),
    )
    trace = next(t for t in output.graph_trace if t.node == "ComparisonRedactor")
    assert trace.outcome in ("deterministic_flag_off", "fallback_deterministic")
    assert "MARVO 20" in (output.answer_text or "")
