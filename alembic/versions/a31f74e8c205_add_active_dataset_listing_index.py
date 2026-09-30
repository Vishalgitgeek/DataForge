"""add active dataset listing index

Revision ID: a31f74e8c205
Revises: d7a4f9c2b681
Create Date: 2026-10-01 04:02:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a31f74e8c205"
down_revision: Union[str, None] = "d7a4f9c2b681"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_datasets_active_owner_created_id",
        "datasets",
        [
            "owner_id",
            sa.text("created_at DESC"),
            sa.text("id DESC"),
        ],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_datasets_active_owner_created_id",
        table_name="datasets",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
