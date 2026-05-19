"""add merchant billing columns

Adds stripe_billing_customer_id, subscription_id, and subscription_status
to the merchants table to support the $99/month Stripe Subscription billing.

Revision ID: d8f4e2c1a9b3
Revises: c3e7f2a9b1d4
Create Date: 2026-05-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d8f4e2c1a9b3"
down_revision: str | Sequence[str] | None = "c3e7f2a9b1d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("merchants") as batch_op:
        batch_op.add_column(sa.Column("stripe_billing_customer_id", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("subscription_id", sa.Text, nullable=True))
        batch_op.add_column(
            sa.Column("subscription_status", sa.Text, server_default="inactive", nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("merchants") as batch_op:
        batch_op.drop_column("subscription_status")
        batch_op.drop_column("subscription_id")
        batch_op.drop_column("stripe_billing_customer_id")
