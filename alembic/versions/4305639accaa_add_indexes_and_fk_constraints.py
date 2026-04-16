"""add indexes and fk constraints

Performance indexes for dashboard queries and API key lookups.
Foreign key constraints for referential integrity.

Revision ID: 4305639accaa
Revises: 9db10166ac38
Create Date: 2026-04-16
"""
from typing import Sequence, Union

from alembic import op


revision: str = '4305639accaa'
down_revision: Union[str, Sequence[str], None] = '9db10166ac38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Performance indexes ──────────────────────────────────────────────
    op.create_index('ix_transactions_merchant_created', 'transactions', ['merchant_id', 'created_at'])
    op.create_index('ix_transactions_user_id', 'transactions', ['user_id'])
    op.create_index('ix_merchants_api_key_hash', 'merchants', ['api_key_hash'])
    op.create_index('ix_verification_codes_lookup', 'customer_verification_codes', ['email', 'code', 'used'])
    op.create_index('ix_fingerprints_user_id', 'fingerprints', ['user_id'])

    # ── Foreign key constraints ──────────────────────────────────────────
    # Note: SQLite does not enforce FK constraints added via ALTER TABLE.
    # These are effective on Postgres only.
    with op.batch_alter_table('fingerprints') as batch_op:
        batch_op.create_foreign_key('fk_fingerprints_user', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('transactions') as batch_op:
        batch_op.create_foreign_key('fk_transactions_user', 'users', ['user_id'], ['id'])
        batch_op.create_foreign_key('fk_transactions_merchant', 'merchants', ['merchant_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('transactions') as batch_op:
        batch_op.drop_constraint('fk_transactions_merchant', type_='foreignkey')
        batch_op.drop_constraint('fk_transactions_user', type_='foreignkey')

    with op.batch_alter_table('fingerprints') as batch_op:
        batch_op.drop_constraint('fk_fingerprints_user', type_='foreignkey')

    op.drop_index('ix_fingerprints_user_id', 'fingerprints')
    op.drop_index('ix_verification_codes_lookup', 'customer_verification_codes')
    op.drop_index('ix_merchants_api_key_hash', 'merchants')
    op.drop_index('ix_transactions_user_id', 'transactions')
    op.drop_index('ix_transactions_merchant_created', 'transactions')
