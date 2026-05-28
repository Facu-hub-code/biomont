"""MetaFilter (spec 003): determina kinds a permitir segun intent."""

from __future__ import annotations

from dataclasses import dataclass

from biomont_common.schemas.agent_graph import Intent
from biomont_common.schemas.knowledge import DocumentKind

from app.agent.graph.nodes._helpers import trace_node


@dataclass
class MetaFilterNode:
    full_corpus_for_all_intents: bool = False

    async def __call__(self, state: dict) -> dict:
        intent = state.get("intent")
        updates: dict = {}
        all_kinds = list(DocumentKind)
        with trace_node(updates, node="MetaFilter") as result:
            if self.full_corpus_for_all_intents:
                kinds = all_kinds
            elif intent == Intent.clinical_protocol:
                kinds = [DocumentKind.bitacora, DocumentKind.balotario]
            elif intent == Intent.dosage_question:
                kinds = [
                    DocumentKind.bitacora,
                    DocumentKind.ficha_tecnica,
                    DocumentKind.balotario,
                ]
            elif intent == Intent.safety_question:
                kinds = [
                    DocumentKind.ficha_tecnica,
                    DocumentKind.bitacora,
                    DocumentKind.balotario,
                ]
            elif intent == Intent.comparison_with_competitor:
                kinds = [DocumentKind.bitacora]
            else:
                kinds = None
            result["outcome"] = "filtered"
            result["payload"] = {
                "kinds": [k.value for k in kinds] if kinds else None,
            }
            updates["filter_kinds"] = kinds
        return updates
