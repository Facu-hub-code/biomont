"""Pool asyncpg compartido con soporte para pgvector."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
from pgvector.asyncpg import register_vector

from biomont_common.logging import get_logger
from biomont_common.settings import DatabaseSettings, get_database_settings

_logger = get_logger("db.pool")


async def register_pgvector(connection: asyncpg.Connection) -> None:
    """Registra el tipo `vector` en la conexion."""

    await register_vector(connection)


class DatabasePool:
    """Wrapper minimo sobre `asyncpg.Pool` para encapsular su ciclo de vida.

    Sigue `.cursor/rules/dependency-constraints.mdc`: no se crean clientes
    globales en import-time; se construyen via factory.
    """

    def __init__(self, settings: DatabaseSettings | None = None) -> None:
        self._settings = settings or get_database_settings()
        self._pool: asyncpg.Pool | None = None

    async def start(self) -> None:
        if self._pool is not None:
            return
        dsn = self._settings.database_url.get_secret_value()
        _logger.info(
            "db_pool_starting",
            action="startup",
            min_size=self._settings.pool_min_size,
            max_size=self._settings.pool_max_size,
        )
        self._pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=self._settings.pool_min_size,
            max_size=self._settings.pool_max_size,
            init=register_pgvector,
            command_timeout=self._settings.statement_timeout_ms / 1000,
        )

    async def stop(self) -> None:
        if self._pool is None:
            return
        await self._pool.close()
        self._pool = None
        _logger.info("db_pool_stopped", action="shutdown")

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        if self._pool is None:
            raise RuntimeError("DatabasePool no fue iniciado")
        async with self._pool.acquire() as connection:
            yield connection

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[asyncpg.Connection]:
        async with self.acquire() as connection:
            async with connection.transaction():
                yield connection


def create_pool(settings: DatabaseSettings | None = None) -> DatabasePool:
    return DatabasePool(settings)
