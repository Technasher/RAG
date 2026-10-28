"""add file fields to documents

Revision ID: 58bfa7cb42d8
Revises: 72f6427c77d9
Create Date: 2026-10-28 03:57:45.287347

"""
import pgvector
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '58bfa7cb42d8'
down_revision: Union[str, Sequence[str], None] = '72f6427c77d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("file_path", sa.String(512), nullable=True))
    op.add_column("documents", sa.Column("file_mime", sa.String(128), nullable=True))
    op.add_column("documents", sa.Column("file_size", sa.BigInteger(), nullable=True))
    op.add_column("documents", sa.Column("file_name", sa.String(512), nullable=True))


def downgrade() -> None:
    for col in ("file_path", "file_mime", "file_size", "file_name"):
        op.drop_column("documents", col)
