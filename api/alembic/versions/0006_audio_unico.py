"""Un solo audio por canción y tipo: `unique(song_id, kind)` en `audio_assets`.

Revision ID: 0006
Revises: 0005
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_audio_assets_song_kind", "audio_assets", ["song_id", "kind"])


def downgrade() -> None:
    op.drop_constraint("uq_audio_assets_song_kind", "audio_assets", type_="unique")
