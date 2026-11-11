"""Add application users and document visibility.

Revision ID: 5ea1d0f94c2b
Revises: cd93f8db2250
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "5ea1d0f94c2b"
down_revision: str | Sequence[str] | None = "cd93f8db2250"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_app_users_username", "app_users", ["username"], unique=True)
    op.add_column(
        "document_chunks",
        sa.Column("visibility", sa.String(length=32), server_default="public", nullable=False),
    )
    op.create_index(
        "ix_document_chunks_visibility", "document_chunks", ["visibility"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_visibility", table_name="document_chunks")
    op.drop_column("document_chunks", "visibility")
    op.drop_index("ix_app_users_username", table_name="app_users")
    op.drop_table("app_users")
