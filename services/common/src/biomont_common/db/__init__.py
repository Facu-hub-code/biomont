"""Acceso compartido a Postgres + pgvector."""

from biomont_common.db.conversation_state_repository import (
    ConversationStateRepository,
)
from biomont_common.db.faq_repository import FaqInput, FaqRepository
from biomont_common.db.pool import (
    DatabasePool,
    create_pool,
    register_pgvector,
)
from biomont_common.db.product_repository import (
    ProductRepository,
    normalize_text,
)

__all__ = [
    "ConversationStateRepository",
    "DatabasePool",
    "FaqInput",
    "FaqRepository",
    "ProductRepository",
    "create_pool",
    "normalize_text",
    "register_pgvector",
]
