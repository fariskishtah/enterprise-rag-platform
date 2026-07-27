"""Add public-demo lifecycle metadata.

Revision ID: 0004_public_demo_lifecycle
Revises: 0003_media_intelligence
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_public_demo_lifecycle"
down_revision: str | None = "0003_media_intelligence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("knowledge_bases", "documents", "media_sources")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column(
                "last_accessed_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.current_timestamp(),
                nullable=False,
            ),
        )
        op.add_column(table, sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(
            table,
            sa.Column("is_protected", sa.Boolean(), server_default=sa.false(), nullable=False),
        )
        op.create_index(f"ix_{table}_expires_at", table, ["expires_at"])


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_index(f"ix_{table}_expires_at", table_name=table)
        op.drop_column(table, "is_protected")
        op.drop_column(table, "expires_at")
        op.drop_column(table, "last_accessed_at")
