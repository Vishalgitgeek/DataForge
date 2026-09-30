"""add dataset version listing index

Revision ID: b6c8e2a41d73
Revises: a31f74e8c205
Create Date: 2026-10-01 04:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b6c8e2a41d73"
down_revision: Union[str, None] = "a31f74e8c205"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_dataset_versions_dataset_created_id",
        "dataset_versions",
        [
            "dataset_id",
            sa.text("created_at DESC"),
            sa.text("id DESC"),
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dataset_versions_dataset_created_id",
        table_name="dataset_versions",
    )
