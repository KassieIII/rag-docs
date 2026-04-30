"""Switch documents.created_at to TIMESTAMP WITH TIME ZONE

Revision ID: 0003_created_at_tz
Revises: 0002_hnsw
Create Date: 2026-04-30 09:00:00

Notes:
    The model defaults ``created_at`` to ``datetime.now(UTC)`` (timezone-aware).
    The original column was ``TIMESTAMP WITHOUT TIME ZONE`` which asyncpg
    rejects with "can't subtract offset-naive and offset-aware datetimes".
    Switch to ``timestamptz`` which is the right choice for any timestamp
    that is meaningful across regions / DST boundaries anyway.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003_created_at_tz"
down_revision: str | None = "0002_hnsw"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.alter_column(
        "documents",
        "created_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(timezone=False),
        existing_server_default=sa.text("now()"),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "documents",
        "created_at",
        type_=sa.DateTime(timezone=False),
        existing_type=sa.DateTime(timezone=True),
        existing_server_default=sa.text("now()"),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
