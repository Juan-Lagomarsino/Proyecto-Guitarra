"""Preferencias de forma de acorde aprendidas de las ediciones: tabla `chord_shape_preferences`.

Una fila por instrumento; `weights` es `{acorde: {forma: peso}}` (ver core).

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chord_shape_preferences",
        sa.Column("instrument", sa.String(20), primary_key=True),
        sa.Column("weights", postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("instrument IN ('classical', 'electric')", name="instrument_valid"),
    )


def downgrade() -> None:
    op.drop_table("chord_shape_preferences")
