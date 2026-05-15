"""replace fingerprint descriptor with per-blob storage

Drops the single descriptor column and replaces it with four individually
encrypted 318-byte feature blob columns (descriptor_0..3).

Existing rows use the 1632-byte DP template format, which cannot be
decomposed back into 4 x 318-byte pre-reg feature blobs. They are deleted
before the column change — affected users must re-enroll.

Revision ID: c3e7f2a9b1d4
Revises: 4305639accaa
Create Date: 2026-05-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3e7f2a9b1d4"
down_revision: str | Sequence[str] | None = "4305639accaa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing rows hold 1632-byte DP enrollment templates, which cannot be
    # split back into the 4 x 318-byte pre-reg feature blobs the new schema
    # requires. Delete them now; affected users must re-enroll.
    op.execute("DELETE FROM fingerprints")

    with op.batch_alter_table("fingerprints") as batch_op:
        batch_op.drop_column("descriptor")
        batch_op.add_column(sa.Column("descriptor_0", sa.LargeBinary, nullable=False))
        batch_op.add_column(sa.Column("descriptor_1", sa.LargeBinary, nullable=False))
        batch_op.add_column(sa.Column("descriptor_2", sa.LargeBinary, nullable=False))
        batch_op.add_column(sa.Column("descriptor_3", sa.LargeBinary, nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("fingerprints") as batch_op:
        batch_op.drop_column("descriptor_3")
        batch_op.drop_column("descriptor_2")
        batch_op.drop_column("descriptor_1")
        batch_op.drop_column("descriptor_0")
        # Restored as nullable — the deleted rows cannot be recovered.
        batch_op.add_column(sa.Column("descriptor", sa.LargeBinary, nullable=True))
