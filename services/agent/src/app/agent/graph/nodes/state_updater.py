"""StateUpdater (spec 003): persiste el estado conversacional."""

from __future__ import annotations

from dataclasses import dataclass

from biomont_common.db.conversation_state_repository import (
    ConversationStateRepository,
)

from app.agent.graph.nodes._helpers import trace_node


@dataclass
class StateUpdaterNode:
    repository: ConversationStateRepository

    async def __call__(self, state: dict) -> dict:
        conversation_id = state.get("conversation_id")
        updates: dict = {"state_updated": False}
        with trace_node(updates, node="StateUpdater") as result:
            if conversation_id is None:
                result["outcome"] = "no_conversation"
                return updates

            intent = state.get("intent")
            await self.repository.upsert(
                conversation_id=conversation_id,
                current_product_id=state.get("product_id"),
                current_topic=intent.value if intent is not None else None,
                current_species=state.get("current_species"),
                last_intent=intent.value if intent is not None else None,
            )
            result["outcome"] = "updated"
            updates["state_updated"] = True
        return updates
