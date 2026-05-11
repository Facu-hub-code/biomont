"""Acceso compartido a Postgres + pgvector."""

from biomont_common.db.pool import (
    DatabasePool,
    create_pool,
    register_pgvector,
)

__all__ = ["DatabasePool", "create_pool", "register_pgvector"]
