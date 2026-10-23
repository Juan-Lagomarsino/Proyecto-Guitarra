"""Versiones de usuario descartables: `song_charts.discarded_at`.

Volver a la versión automática no borra la edición del usuario (el historial de correcciones
queda); la marca como descartada y deja de ganar en `GET chart`.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("song_charts", sa.Column("discarded_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("song_charts", "discarded_at")
