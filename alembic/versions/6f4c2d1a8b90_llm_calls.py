"""Add the LLM call cost ledger.

Revision ID: 6f4c2d1a8b90
Revises: 5ea1d0f94c2b
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "6f4c2d1a8b90"
down_revision: str | Sequence[str] | None = "5ea1d0f94c2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("endpoint", sa.String(length=32), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=False),
        sa.Column("cost_eur", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_calls_endpoint", "llm_calls", ["endpoint"], unique=False)
    op.create_index("ix_llm_calls_username", "llm_calls", ["username"], unique=False)
    op.create_index("ix_llm_calls_run_id", "llm_calls", ["run_id"], unique=False)
    op.create_index("ix_llm_calls_created_at", "llm_calls", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_llm_calls_created_at", table_name="llm_calls")
    op.drop_index("ix_llm_calls_run_id", table_name="llm_calls")
    op.drop_index("ix_llm_calls_username", table_name="llm_calls")
    op.drop_index("ix_llm_calls_endpoint", table_name="llm_calls")
    op.drop_table("llm_calls")
