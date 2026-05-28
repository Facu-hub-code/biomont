"""MetaFilter con mapa de kinds desde config (spec 008)."""

import pytest

from biomont_common.schemas.agent_graph import Intent

from app.agent.graph.nodes.meta_filter import MetaFilterNode


@pytest.mark.asyncio
async def test_meta_filter_uses_db_kinds_map() -> None:
    node = MetaFilterNode(full_corpus_for_all_intents=False)
    state = {
        "intent": Intent.clinical_protocol,
        "runtime_full_corpus": False,
        "intent_kinds_by_slug": {
            "clinical_protocol": ["bitacora", "balotario"],
        },
        "trace": [],
    }
    updates = await node(state)
    kinds = updates["filter_kinds"]
    assert kinds is not None
    assert {k.value for k in kinds} == {"bitacora", "balotario"}


@pytest.mark.asyncio
async def test_meta_filter_full_corpus_from_runtime_flag() -> None:
    node = MetaFilterNode(full_corpus_for_all_intents=False)
    state = {
        "intent": Intent.clinical_protocol,
        "runtime_full_corpus": True,
        "intent_kinds_by_slug": {"clinical_protocol": ["bitacora"]},
        "trace": [],
    }
    updates = await node(state)
    kinds = updates["filter_kinds"]
    assert kinds is not None
    assert len(kinds) == 3
