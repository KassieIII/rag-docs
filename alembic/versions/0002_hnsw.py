"""HNSW index on chunks.embedding for sub-linear vector search

Revision ID: 0002_hnsw
Revises: 0001_init
Create Date: 2026-04-15 19:40:00

Notes:
    pgvector 0.5+ ships HNSW. We pick m=16, ef_construction=64 which is the
    common starting point for ~1M vectors at 384 dim. ``vector_cosine_ops``
    matches our normalized embeddings; we never use L2 here.
"""
from __future__ import annotations

from alembic import op

revision: str = "0002_hnsw"
down_revision: str | None = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw
        ON chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
