"""Tests de CompetitorResolver (spec 012)."""

from __future__ import annotations

import uuid

import pytest

from biomont_common.schemas.comparison import Competitor
from biomont_common.schemas.products import ProductCandidate

from app.agent.graph.nodes.competitor_resolver import CompetitorResolverNode


class _FakeProductRepo:
    def __init__(self, candidates_by_query: dict[str, list[ProductCandidate]]):
        self._candidates = candidates_by_query

    async def search_candidates(self, query: str, *, allowed_countries, limit=5):
        key = query.strip().lower()
        for pattern, items in self._candidates.items():
            if pattern in key or key.startswith(pattern):
                return items[:limit]
        return self._candidates.get("__default__", [])[:limit]


class _FakeComparisonRepo:
    def __init__(self, competitors_by_token: dict[str, list[Competitor]]):
        self._competitors = competitors_by_token

    async def find_competitor_by_query(self, query: str, limit: int = 5):
        nq = query.strip().lower()
        for token, items in self._competitors.items():
            if token in nq:
                return items[:limit]
        return []


@pytest.mark.asyncio
async def test_resolver_prefers_bravecto_over_protego_m_on_full_query() -> None:
    protego_3m = uuid.uuid4()
    protego_m = uuid.uuid4()
    bravecto = Competitor(
        id=uuid.uuid4(),
        name="Bravecto",
        brand=None,
        is_internal=False,
    )
    node = CompetitorResolverNode(
        comparison_repository=_FakeComparisonRepo(
            {
                "bravecto": [bravecto],
                "protego m": [
                    Competitor(
                        id=uuid.uuid4(),
                        name="Proteggo M",
                        brand=None,
                        is_internal=False,
                    )
                ],
            }
        ),
        product_repository=_FakeProductRepo(
            {
                "proteggo 3m versus bravecto": [
                    ProductCandidate(
                        product_id=protego_3m,
                        product_name="Protego 3M",
                        alias_matched="protego 3m",
                        similarity=0.95,
                    ),
                    ProductCandidate(
                        product_id=protego_m,
                        product_name="Protego M",
                        alias_matched="protego m",
                        similarity=0.85,
                    ),
                ],
                "bravecto": [],
            }
        ),
    )
    state = {
        "query": "Proteggo 3M versus Bravecto diferencias",
        "product_id": protego_3m,
        "product_name": "Protego 3M",
    }
    updates = await node(state)
    assert updates.get("competitor_name") == "Bravecto"
    assert updates.get("competitor_is_internal") is False
    assert "answer_text" not in updates


@pytest.mark.asyncio
async def test_resolver_internal_protego_m_from_tail_after_versus() -> None:
    protego_3m = uuid.uuid4()
    protego_m = uuid.uuid4()
    node = CompetitorResolverNode(
        comparison_repository=_FakeComparisonRepo({}),
        product_repository=_FakeProductRepo(
            {
                "protego m": [
                    ProductCandidate(
                        product_id=protego_m,
                        product_name="Protego M",
                        alias_matched="protego m",
                        similarity=0.92,
                    ),
                ],
            }
        ),
    )
    state = {
        "query": "Protego 3M versus Protego M diferencias",
        "product_id": protego_3m,
        "product_name": "Protego 3M",
    }
    updates = await node(state)
    assert updates.get("competitor_name") == "Protego M"
    assert updates.get("competitor_is_internal") is True
    assert updates.get("competitor_product_id") == protego_m


@pytest.mark.asyncio
async def test_resolver_does_not_pick_protego_m_from_subject_side_of_query() -> None:
    protego_3m = uuid.uuid4()
    protego_m = uuid.uuid4()
    bravecto = Competitor(
        id=uuid.uuid4(),
        name="Bravecto",
        brand=None,
        is_internal=False,
    )
    node = CompetitorResolverNode(
        comparison_repository=_FakeComparisonRepo({"bravecto": [bravecto]}),
        product_repository=_FakeProductRepo(
            {
                "bravecto diferencias": [],
                "proteggo 3m versus bravecto diferencias": [
                    ProductCandidate(
                        product_id=protego_3m,
                        product_name="Protego 3M",
                        alias_matched="x",
                        similarity=0.95,
                    ),
                    ProductCandidate(
                        product_id=protego_m,
                        product_name="Protego M",
                        alias_matched="y",
                        similarity=0.88,
                    ),
                ],
            }
        ),
    )
    state = {
        "query": "Proteggo 3M versus Bravecto diferencias",
        "product_id": protego_3m,
        "product_name": "Protego 3M",
    }
    updates = await node(state)
    assert updates.get("competitor_name") == "Bravecto"
