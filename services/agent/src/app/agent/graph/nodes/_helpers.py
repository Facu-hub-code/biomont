"""Helpers compartidos entre nodos del grafo (timing + trace)."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator

from biomont_common.schemas.agent_graph import GraphNodeTrace


@contextmanager
def trace_node(
    updates: dict[str, Any],
    *,
    node: str,
    outcome: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    """Context manager que registra la entrada de trace en `updates['trace']`.

    LangGraph usa `Annotated[list, operator.add]` como reducer para
    `trace`, por lo que cada nodo emite SOLO su propia entry (lista de
    1) y langgraph concatena. El nodo construye su dict de updates
    pasandoselo a este context manager; al salir, se agrega
    `updates['trace'] = [entry]`.

    Uso:
        async def __call__(self, state):
            updates = {}
            with trace_node(updates, node='HybridRetriever') as result:
                result['outcome'] = 'retrieved'
            return updates
    """

    started = time.perf_counter()
    result: dict[str, Any] = {"outcome": outcome, "payload": payload}
    try:
        yield result
    finally:
        latency_ms = int((time.perf_counter() - started) * 1000)
        entry = GraphNodeTrace(
            node=node,
            latency_ms=latency_ms,
            outcome=result.get("outcome"),
            payload=result.get("payload"),
        )
        updates["trace"] = [entry]
