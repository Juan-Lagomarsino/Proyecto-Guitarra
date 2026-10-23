import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from guitarra_api.domain.song_chart import SongChartContent, overall_confidence
from guitarra_api.infra.db.models import AnalysisJob, Exercise, Song, SongChart, SongSection

USER_ORIGIN = "user"
ACTIVE_JOB_STATUSES = ("queued", "running")


def normalize_text(text: str) -> str:
    """Minúsculas, sin tildes y con los espacios recortados y colapsados."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(without_marks.split())


class SongRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def stage_song(
        self,
        *,
        title: str | None,
        artist: str | None,
        source: str,
        url: str | None = None,
        youtube_id: str | None = None,
        spotify_id: str | None = None,
    ) -> Song:
        """Agrega la canción y hace flush (asigna id y detecta duplicados), sin commit."""
        song = Song(
            title=title,
            artist=artist,
            source=source,
            url=url,
            youtube_id=youtube_id,
            spotify_id=spotify_id,
        )
        self._session.add(song)
        self._session.flush()
        return song

    def add_song(self, **fields) -> Song:
        song = self.stage_song(**fields)
        self._session.commit()
        return song

    def get(self, song_id: int) -> Song | None:
        return self._session.get(Song, song_id)

    def get_by_youtube_id(self, youtube_id: str) -> Song | None:
        return self._session.scalar(select(Song).where(Song.youtube_id == youtube_id))

    def get_by_spotify_id(self, spotify_id: str) -> Song | None:
        return self._session.scalar(select(Song).where(Song.spotify_id == spotify_id))

    def find_by_title_artist(self, title: str, artist: str) -> Song | None:
        """Canción de búsqueda por nombre con el mismo título y artista, normalizados."""
        wanted = (normalize_text(title), normalize_text(artist))
        candidates = self._session.scalars(
            select(Song).where(Song.source == "search").order_by(Song.id)
        )
        return next(
            (
                song
                for song in candidates
                if (normalize_text(song.title or ""), normalize_text(song.artist or "")) == wanted
            ),
            None,
        )

    def list_songs(self) -> list[Song]:
        return list(self._session.scalars(select(Song).order_by(Song.created_at.desc(), Song.id)))

    def add_chart(self, song_id: int, origin: str, content: SongChartContent) -> SongChart:
        """Guarda un chart con la versión siguiente de su canción e instrumento.

        La confianza global se calcula del contenido. La restricción única de la base protege
        contra dos altas simultáneas que calculen la misma versión.
        """
        chart = self.stage_chart(song_id, origin, content)
        self._session.commit()
        return chart

    def stage_chart(self, song_id: int, origin: str, content: SongChartContent) -> SongChart:
        """Como `add_chart` pero sin commit, para sumarlo a una transacción más grande."""
        chart = SongChart(
            song_id=song_id,
            instrument=content.instrument,
            version=self._next_version(song_id, content.instrument),
            origin=origin,
            content=content.model_dump(mode="json"),
            confidence=overall_confidence(content),
        )
        self._session.add(chart)
        self._session.flush()
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

    def get_section(self, song_id: int, section_id: int) -> SongSection | None:
        """La sección solo si pertenece a esa canción."""
        return self._session.scalar(
            select(SongSection).where(SongSection.id == section_id, SongSection.song_id == song_id)
        )

    def add_exercise(self, exercise: Exercise) -> Exercise:
        """Agrega el ejercicio y hace flush, sin commit."""
        self._session.add(exercise)
        self._session.flush()
        return exercise

    def list_exercises(self, song_id: int) -> list[Exercise]:
        """Ejercicios de todas las secciones de la canción, del más viejo al más nuevo."""
        query = (
            select(Exercise)
            .join(SongSection, Exercise.song_section_id == SongSection.id)
            .where(SongSection.song_id == song_id)
            .order_by(Exercise.id)
        )
        return list(self._session.scalars(query))

    def active_job(self, song_id: int) -> AnalysisJob | None:
        """El trabajo `queued` o `running` de la canción, si hay."""
        return self._session.scalar(
            select(AnalysisJob)
            .where(AnalysisJob.song_id == song_id, AnalysisJob.status.in_(ACTIVE_JOB_STATUSES))
            .order_by(AnalysisJob.id.desc())
            .limit(1)
        )

    def latest_job(self, song_id: int) -> AnalysisJob | None:
        return self._session.scalar(
            select(AnalysisJob)
            .where(AnalysisJob.song_id == song_id)
            .order_by(AnalysisJob.id.desc())
            .limit(1)
        )

    def _next_version(self, song_id: int, instrument: str) -> int:
        latest = self._session.scalar(
            select(func.max(SongChart.version)).where(
                SongChart.song_id == song_id, SongChart.instrument == instrument
            )
        )
        return (latest or 0) + 1
