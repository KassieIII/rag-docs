"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

RetrieveMode = Literal["vector", "bm25", "hybrid"]


class Settings(BaseSettings):
    """Runtime settings.

    Values come from environment variables (or a local ``.env`` file in dev).
    Anything sensitive (API keys, hosts) lives here, not in code.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://rag:rag@localhost:5432/ragdocs",
        description="Async SQLAlchemy URL pointing at a Postgres+pgvector instance.",
    )

    # --- Embeddings -------------------------------------------------------
    embed_model: str = Field(
        default="BAAI/bge-small-en-v1.5",
        description="sentence-transformers model id. 384-dim by default.",
    )
    embed_dim: int = Field(default=384, ge=64, le=4096)
    embed_batch_size: int = Field(default=32, ge=1, le=512)

    # --- LLM (Ollama) -----------------------------------------------------
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3.2:3b")
    llm_timeout_s: float = Field(default=60.0, ge=1.0)

    # --- Retrieval --------------------------------------------------------
    retrieve_top_k: int = Field(default=5, ge=1, le=50)
    retrieve_score_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    retrieve_mode: RetrieveMode = Field(
        default="hybrid",
        description=(
            "Retrieval strategy: 'vector' (pgvector cosine), 'bm25' "
            "(Postgres FTS via ts_rank_cd), or 'hybrid' (both fused with "
            "Reciprocal Rank Fusion). Hybrid is the default because it "
            "is robust to exact-match terms (function names, versions) "
            "that pure embeddings sometimes miss."
        ),
    )
    rerank_enabled: bool = Field(default=False)

    # --- Chunking ---------------------------------------------------------
    chunk_size: int = Field(default=800, ge=100, le=4000)
    chunk_overlap: int = Field(default=100, ge=0, le=2000)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()
