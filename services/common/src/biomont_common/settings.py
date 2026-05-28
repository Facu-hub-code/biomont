"""Settings compartidos.

Cada servicio puede extender estos bloques con su propio `Settings`. Los
valores se cargan desde variables de entorno y desde `.env` cuando esta
presente.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Datos de conexion al Postgres remoto (Railway)."""

    database_url: SecretStr = Field(..., alias="DATABASE_URL")
    pool_min_size: int = Field(1, alias="DB_POOL_MIN_SIZE")
    pool_max_size: int = Field(10, alias="DB_POOL_MAX_SIZE")
    statement_timeout_ms: int = Field(15_000, alias="DB_STATEMENT_TIMEOUT_MS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


class OpenAISettings(BaseSettings):
    """Credenciales y modelos OpenAI."""

    api_key: SecretStr = Field(..., alias="OPENAI_API_KEY")
    chat_model: str = Field("gpt-4o-mini", alias="OPENAI_CHAT_MODEL")
    embeddings_model: str = Field(
        "text-embedding-3-small", alias="OPENAI_EMBEDDINGS_MODEL"
    )
    # Dim parametrizable: 1536 (3-small), 3072 (3-large). Si cambia, requiere
    # reingesta total del corpus (los chunks viejos quedan incomparables).
    embeddings_dim: int = Field(1536, alias="OPENAI_EMBEDDINGS_DIM")
    request_timeout_s: float = Field(30.0, alias="OPENAI_REQUEST_TIMEOUT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


class LoggingSettings(BaseSettings):
    """Logging estructurado (structlog)."""

    level: str = Field("INFO", alias="LOG_LEVEL")
    json_output: bool = Field(True, alias="LOG_JSON")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


class RagSettings(BaseSettings):
    """Settings del pipeline RAG y del grafo del agente (spec 003).

    Todos los pesos y umbrales son hot-tunables por env sin redeploy de
    schema. Si se cambia `embeddings_dim` desde `OpenAISettings`, requiere
    reingesta total.
    """

    # Fusion hibrida vector + BM25.
    vector_weight: float = Field(0.7, alias="RAG_VECTOR_WEIGHT")
    bm25_weight: float = Field(0.3, alias="RAG_BM25_WEIGHT")
    top_k: int = Field(6, alias="RAG_TOP_K")
    candidate_k: int = Field(25, alias="RAG_CANDIDATE_K")

    # Product resolver deterministico (pg_trgm + aliases).
    product_resolver_threshold: float = Field(
        0.55, alias="PRODUCT_RESOLVER_THRESHOLD"
    )
    product_resolver_margin: float = Field(
        0.10, alias="PRODUCT_RESOLVER_MARGIN"
    )

    # Dev / QA: ignora filtros de tipo de documento por intent.
    full_corpus_for_all_intents: bool = Field(
        False, alias="RAG_FULL_CORPUS_FOR_ALL_INTENTS"
    )

    # Tamaño de fragmentos `knowledge_chunks` (StructuredMarkdownChunker).
    # Subir mejora contexto por chunk; bajar acota costo de embedding / ruido BM25.
    # Requiere reingesta para aplicar a documentos ya cargados.
    knowledge_chunk_tokens: int = Field(1000, alias="RAG_KNOWLEDGE_CHUNK_TOKENS")
    knowledge_chunk_overlap: int = Field(120, alias="RAG_KNOWLEDGE_CHUNK_OVERLAP")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )


@lru_cache(maxsize=1)
def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()


@lru_cache(maxsize=1)
def get_openai_settings() -> OpenAISettings:
    return OpenAISettings()


@lru_cache(maxsize=1)
def get_logging_settings() -> LoggingSettings:
    return LoggingSettings()


@lru_cache(maxsize=1)
def get_rag_settings() -> RagSettings:
    return RagSettings()
