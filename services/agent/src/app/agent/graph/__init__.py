"""Grafo LangGraph del agente (spec 003).

El grafo reemplaza al pipeline LCEL cuando `AGENT_USE_GRAPH=true`,
permitiendo enrutamiento condicional (FAQ directo vs hibrido,
ambiguous vs resolved) y trazabilidad por nodo.

El nodo `Calculator` queda declarado como placeholder y no se enruta en
v1 (spec 003, "Fuera de alcance").
"""

from app.agent.graph.graph import GraphOutput, GraphPipeline, build_graph
from app.agent.graph.state import AgentGraphState

__all__ = ["AgentGraphState", "GraphOutput", "GraphPipeline", "build_graph"]
