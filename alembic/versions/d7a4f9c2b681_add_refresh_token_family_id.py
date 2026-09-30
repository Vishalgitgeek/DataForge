"""add refresh token family id

Revision ID: d7a4f9c2b681
Revises: c1e37e3f22f3
Create Date: 2026-10-01 02:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d7a4f9c2b681"
down_revision: Union[str, None] = "c1e37e3f22f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "refresh_tokens",
        sa.Column("family_id", sa.UUID(), nullable=True),
    )
    op.execute("UPDATE refresh_tokens SET family_id = id WHERE family_id IS NULL")
    op.alter_column("refresh_tokens", "family_id", nullable=False)
    op.create_index(
        "ix_refresh_tokens_family_revoked",
        "refresh_tokens",
        ["family_id", "revoked_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_family_revoked", table_name="refresh_tokens")
    op.drop_column("refresh_tokens", "family_id")
