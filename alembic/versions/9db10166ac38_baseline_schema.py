"""baseline schema

Represents the current schema as of the initial Alembic adoption.
Existing production databases should run `alembic stamp head` to mark
this migration as already applied, then run future migrations normally.

Revision ID: 9db10166ac38
Revises:
Create Date: 2026-04-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9db10166ac38"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("full_name", sa.Text, nullable=False),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("phone", sa.Text),
        sa.Column("stripe_customer_id", sa.Text),
        sa.Column("stripe_payment_method_id", sa.Text),
        sa.Column("enrolled_at", sa.Text, nullable=False),
    )

    op.create_table(
        "fingerprints",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("descriptor", sa.LargeBinary, nullable=False),
        sa.Column("enrolled_at", sa.Text, nullable=False),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("merchant", sa.Text, nullable=False),
        sa.Column("stripe_payment_intent_id", sa.Text),
        sa.Column("stripe_status", sa.Text),
        sa.Column("merchant_id", sa.Integer),
        sa.Column("platform_fee", sa.Float, server_default="0"),
        sa.Column("balance_after", sa.Float, server_default="0"),
        sa.Column("created_at", sa.Text, nullable=False),
    )

    op.create_table(
        "merchants",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("business_name", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("api_key_hash", sa.Text),
        sa.Column("stripe_connect_id", sa.Text),
        sa.Column("stripe_connect_status", sa.Text, server_default="pending"),
        sa.Column("last_monthly_fee_month", sa.Text),
        sa.Column("is_active", sa.Integer, server_default="1"),
        sa.Column("created_at", sa.Text, nullable=False),
    )

    op.create_table(
        "enrollment_sessions",
        sa.Column("session_id", sa.Text, primary_key=True),
        sa.Column("full_name", sa.Text),
        sa.Column("email", sa.Text),
        sa.Column("phone", sa.Text),
        sa.Column("stripe_customer_id", sa.Text),
        sa.Column("stripe_payment_method_id", sa.Text),
        sa.Column("user_id", sa.Integer),
        sa.Column("status", sa.Text, nullable=False, server_default="pending_form"),
        sa.Column("created_at", sa.Text, nullable=False),
    )

    op.create_table(
        "password_reset_tokens",
        sa.Column("token", sa.Text, primary_key=True),
        sa.Column("merchant_id", sa.Integer, nullable=False),
        sa.Column("expires_at", sa.Text, nullable=False),
        sa.Column("used", sa.Integer, server_default="0"),
    )

    op.create_table(
        "customer_verification_codes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("code", sa.Text, nullable=False),
        sa.Column("expires_at", sa.Text, nullable=False),
        sa.Column("used", sa.Integer, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("customer_verification_codes")
    op.drop_table("password_reset_tokens")
    op.drop_table("enrollment_sessions")
    op.drop_table("merchants")
    op.drop_table("transactions")
    op.drop_table("fingerprints")
    op.drop_table("users")
