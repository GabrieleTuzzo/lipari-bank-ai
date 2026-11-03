"""Add beneficiaries, mandates, and cards.

Revision ID: 0002_domain_entities
Revises: 0001_initial
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_domain_entities"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "beneficiaries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("customer_id", sa.String(length=16), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("iban", sa.String(length=34), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_beneficiaries_customer_id", "beneficiaries", ["customer_id"])

    op.create_table(
        "mandates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(length=34), nullable=False),
        sa.Column("beneficiary_id", sa.String(), nullable=False),
        sa.Column("reference", sa.String(length=35), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(
            ["beneficiary_id"],
            ["beneficiaries.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference", name="uq_mandates_reference"),
    )
    op.create_index("ix_mandates_account_id", "mandates", ["account_id"])
    op.create_index("ix_mandates_beneficiary_id", "mandates", ["beneficiary_id"])

    op.create_table(
        "cards",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(length=34), nullable=False),
        sa.Column("plafond", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.CheckConstraint("plafond >= 0", name="ck_cards_plafond_nonnegative"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cards_account_id", "cards", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_cards_account_id", table_name="cards")
    op.drop_table("cards")
    op.drop_index("ix_mandates_beneficiary_id", table_name="mandates")
    op.drop_index("ix_mandates_account_id", table_name="mandates")
    op.drop_table("mandates")
    op.drop_index("ix_beneficiaries_customer_id", table_name="beneficiaries")
    op.drop_table("beneficiaries")
