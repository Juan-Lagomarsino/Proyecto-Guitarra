"""Preferencias de digitación aprendidas de las correcciones de riffs: `fingering_preferences`.

Fila única (id = 1): la mano del usuario es la misma en cualquier instrumento y afinación
(las posiciones se indexan por altura MIDI), así que no hace falta una fila por clave.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fingering_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("weights", postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("id = 1", name="single_row"),
    )


def downgrade() -> None:
    op.drop_table("fingering_preferences")
