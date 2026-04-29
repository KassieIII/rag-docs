"""initial schema with pgvector extension

Revision ID: 0001_init
Revises:
Create Date: 2026-04-09 20:05:00
"""
from __future__ import annotations

import pgvector.sqlalchemy
import sqlalchemy as sa

from alembic import op

revision: str = "0001_init"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source", sa.String(1024), nullable=False, unique=True),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("content_type", sa.String(32), nullable=False, server_default="text/markdown"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_documents_source", "documents", ["source"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("heading", sa.String(512), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(384), nullable=False),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index(
        "ix_chunks_document_ordinal",
        "chunks",
        ["document_id", "ordinal"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_chunks_document_ordinal", table_name="chunks")
    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_documents_source", table_name="documents")
    op.drop_table("documents")
    # we deliberately don't DROP EXTENSION vector — other tables may depend on it
