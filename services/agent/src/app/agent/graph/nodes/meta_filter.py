"""MetaFilter (spec 003/008): determina kinds a permitir segun intent."""

from __future__ import annotations

from dataclasses import dataclass

from biomont_common.schemas.agent_graph import Intent
from biomont_common.schemas.knowledge import DocumentKind

from app.agent.graph.nodes._helpers import trace_node


def _kinds_for_intent(
    intent: Intent | None,
    *,
    full_corpus: bool,
    intent_kinds_by_slug: dict[str, list[str] | None],
) -> list[DocumentKind] | None:
    all_kinds = list(DocumentKind)
    if full_corpus:
        return all_kinds
    if intent is None:
        return None
    slug = intent.value
    if slug in intent_kinds_by_slug:
        raw = intent_kinds_by_slug[slug]
        if not raw:
            return None
        return [DocumentKind(k) for k in raw]
    return None


@dataclass
class MetaFilterNode:
    full_corpus_for_all_intents: bool = False

    async def __call__(self, state: dict) -> dict:
        intent = state.get("intent")
        updates: dict = {}
        full_corpus = bool(
            state.get("runtime_full_corpus")
            if state.get("runtime_full_corpus") is not None
            else self.full_corpus_for_all_intents
        )
        kinds_map = state.get("intent_kinds_by_slug") or {}
        with trace_node(updates, node="MetaFilter") as result:
            kinds = _kinds_for_intent(
                intent,
                full_corpus=full_corpus,
                intent_kinds_by_slug=kinds_map,
            )
            result["outcome"] = "filtered"
            result["payload"] = {
                "kinds": [k.value for k in kinds] if kinds else None,
            }
            updates["filter_kinds"] = kinds
        return updates
