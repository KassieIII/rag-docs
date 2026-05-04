"""Add tsvector column + GIN index for BM25 / lexical search

Revision ID: 0004_chunks_tsvector
Revises: 0003_created_at_tz
Create Date: 2026-05-04 09:00:00

Notes:
    Hybrid retrieval needs a lexical signal alongside the vector score,
    so that exact-match terms (function names, version strings, error
    codes) are not lost when a paraphrase scores higher under cosine
    similarity.

    We add a STORED generated tsvector column populated from
    ``chunks.text`` with the ``english`` configuration, plus a GIN
    index. ``ts_rank_cd`` over this column gives us a BM25-style
    lexical score; the application combines it with the vector score
    using Reciprocal Rank Fusion.
"""
from __future__ import annotations

from alembic import op

revision: str = "0004_chunks_tsvector"
down_revision: str | None = "0003_created_at_tz"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE chunks
        ADD COLUMN text_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(text, ''))) STORED
        """
    )
    op.execute(
        "CREATE INDEX ix_chunks_text_tsv ON chunks USING GIN (text_tsv)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_text_tsv")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS text_tsv")
