"""Cifra de Cifra Club cargada a mano (ADR 0012).

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("songs", sa.Column("cifra_text", sa.Text(), nullable=True))
    op.add_column("songs", sa.Column("cifra_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("songs", "cifra_url")
    op.drop_column("songs", "cifra_text")
