from sqlalchemy import func, select
from sqlalchemy.orm import Session

from guitarra_api.domain.song_chart import SongChartContent, overall_confidence
from guitarra_api.infra.db.models import Song, SongChart

USER_ORIGIN = "user"


class SongRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_song(
        self,
        *,
        title: str,
        artist: str,
        source: str,
        url: str | None = None,
        youtube_id: str | None = None,
        spotify_id: str | None = None,
    ) -> Song:
        song = Song(
            title=title,
            artist=artist,
            source=source,
            url=url,
            youtube_id=youtube_id,
            spotify_id=spotify_id,
        )
        self._session.add(song)
        self._session.commit()
        return song

    def get(self, song_id: int) -> Song | None:
        return self._session.get(Song, song_id)

    def get_by_youtube_id(self, youtube_id: str) -> Song | None:
        return self._session.scalar(select(Song).where(Song.youtube_id == youtube_id))

    def get_by_spotify_id(self, spotify_id: str) -> Song | None:
        return self._session.scalar(select(Song).where(Song.spotify_id == spotify_id))

    def list_songs(self) -> list[Song]:
        return list(self._session.scalars(select(Song).order_by(Song.created_at.desc(), Song.id)))

    def add_chart(self, song_id: int, origin: str, content: SongChartContent) -> SongChart:
        """Guarda un chart con la versión siguiente de su canción e instrumento.

        La confianza global se calcula del contenido. La restricción única de la base protege
        contra dos altas simultáneas que calculen la misma versión.
        """
        chart = SongChart(
            song_id=song_id,
            instrument=content.instrument,
            version=self._next_version(song_id, content.instrument),
            origin=origin,
            content=content.model_dump(mode="json"),
            confidence=overall_confidence(content),
        )
        self._session.add(chart)
        self._session.commit()
        return chart

    def current_chart(self, song_id: int, instrument: str) -> SongChart | None:
        """El último chart de origen `user` si existe; si no, el último de los demás orígenes."""
        base = select(SongChart).where(
            SongChart.song_id == song_id, SongChart.instrument == instrument
        )
        latest = SongChart.version.desc()
        return self._session.scalar(
            base.where(SongChart.origin == USER_ORIGIN).order_by(latest).limit(1)
        ) or self._session.scalar(
            base.where(SongChart.origin != USER_ORIGIN).order_by(latest).limit(1)
        )

    def _next_version(self, song_id: int, instrument: str) -> int:
        latest = self._session.scalar(
            select(func.max(SongChart.version)).where(
                SongChart.song_id == song_id, SongChart.instrument == instrument
            )
        )
        return (latest or 0) + 1
