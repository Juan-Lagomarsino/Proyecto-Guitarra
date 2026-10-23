"""Casos de uso de la biblioteca de canciones (Explorar)."""

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from guitarra_api.domain.chart_diff import diff_charts
from guitarra_api.domain.song_chart import SongChartContent
from guitarra_api.domain.song_source import ParsedSongUrl, parse_song_url
from guitarra_api.infra.db.models import Song, SongChart
from guitarra_api.infra.db.repositories.jobs import JobRepository
from guitarra_api.infra.db.repositories.songs import USER_ORIGIN, SongRepository


class SongNotFoundError(Exception):
    def __init__(self, song_id: int) -> None:
        super().__init__(f"Canción {song_id} no existe")


class ChartNotFoundError(Exception):
    def __init__(self, song_id: int, instrument: str) -> None:
        super().__init__(f"La canción {song_id} todavía no tiene chart para {instrument}")


class InstrumentMismatchError(Exception):
    def __init__(self, expected: str, received: str) -> None:
        super().__init__(f"El chart es de {received} pero se pidió {expected}")


class SectionsRemovedError(Exception):
    def __init__(self, section_ids: list[str]) -> None:
        names = ", ".join(f"'{section_id}'" for section_id in section_ids)
        super().__init__(
            f"No se puede quitar ni cambiar el id de las secciones existentes: {names}"
        )


class NoUserChartError(Exception):
    def __init__(self, song_id: int, instrument: str) -> None:
        super().__init__(f"La canción {song_id} no tiene una versión editada para {instrument}")


class AnalysisAlreadyActiveError(Exception):
    def __init__(self, song_id: int) -> None:
        super().__init__(f"La canción {song_id} ya tiene un análisis en cola o en curso")


@dataclass(frozen=True)
class SongEntry:
    """Una canción con el paso del análisis activo y el error del último trabajo."""

    song: Song
    current_step: str | None
    error: str | None = None


@dataclass(frozen=True)
class CreatedSong:
    song: Song
    created: bool


@dataclass(frozen=True)
class CifraSaved:
    song: Song
    reanalysis_queued: bool


class SongService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = SongRepository(session)
        self._jobs = JobRepository(session)

    def add_from_url(self, url: str) -> CreatedSong:
        """Raises: InvalidSongUrlError si el link no es de YouTube ni de un tema de Spotify."""
        parsed = parse_song_url(url)
        return self._add_once(
            lambda: self._find_existing(parsed),
            lambda: self._repo.stage_song(
                title=None,
                artist=None,
                source=parsed.source,
                url=url.strip(),
                youtube_id=parsed.youtube_id,
                spotify_id=parsed.spotify_id,
            ),
        )

    def add_from_name(self, title: str, artist: str) -> CreatedSong:
        return self._add_once(
            lambda: self._repo.find_by_title_artist(title, artist),
            lambda: self._repo.stage_song(title=title, artist=artist, source="search"),
        )

    def list_songs(self) -> list[SongEntry]:
        return [self._entry(song) for song in self._repo.list_songs()]

    def get_detail(self, song_id: int) -> SongEntry:
        return self._entry(self._get(song_id))

    def current_chart(self, song_id: int, instrument: str) -> SongChart:
        self._get(song_id)
        chart = self._repo.current_chart(song_id, instrument)
        if chart is None:
            raise ChartNotFoundError(song_id, instrument)
        return chart

    def save_user_chart(
        self, song_id: int, instrument: str, content: SongChartContent
    ) -> SongChart:
        """Guarda el chart editado como versión de usuario y registra qué cambió.

        Sin cambios respecto de la versión vigente no crea nada y devuelve la vigente.
        Raises: ChartNotFoundError si todavía no hay chart que corregir; InstrumentMismatchError.
        """
        if content.instrument != instrument:
            raise InstrumentMismatchError(instrument, content.instrument)
        current = self.current_chart(song_id, instrument)
        diff = diff_charts(current.content, content.model_dump(mode="json"))
        if removed := diff.get("sections_removed"):
            raise SectionsRemovedError(removed)
        if not diff:
            return current
        try:
            chart = self._repo.stage_chart(song_id, USER_ORIGIN, content)
            self._repo.stage_correction(chart, diff)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return chart

    def discard_user_chart(self, song_id: int, instrument: str) -> SongChart:
        """Vuelve a la versión automática. Raises: NoUserChartError si no había edición."""
        self._get(song_id)
        if self._repo.discard_user_charts(song_id, instrument) == 0:
            raise NoUserChartError(song_id, instrument)
        self._session.commit()
        return self.current_chart(song_id, instrument)

    def reanalyze(self, song_id: int) -> Song:
        song = self._get(song_id)
        if self._repo.active_job(song_id) is not None:
            raise AnalysisAlreadyActiveError(song_id)
        return self._queued(song)

    def save_cifra(self, song_id: int, text: str, url: str | None) -> CifraSaved:
        """Guarda la cifra pegada a mano y encola un reanálisis si no hay uno activo."""
        song = self._get(song_id)
        song.cifra_text, song.cifra_url = text, url
        queued = self._repo.active_job(song_id) is None
        try:
            if queued:
                self._jobs.stage_job(song_id)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return CifraSaved(song, reanalysis_queued=queued)

    def delete_cifra(self, song_id: int) -> None:
        song = self._get(song_id)
        song.cifra_text, song.cifra_url = None, None
        self._session.commit()

    def _get(self, song_id: int) -> Song:
        song = self._repo.get(song_id)
        if song is None:
            raise SongNotFoundError(song_id)
        return song

    def _find_existing(self, parsed: ParsedSongUrl) -> Song | None:
        if parsed.youtube_id is not None:
            return self._repo.get_by_youtube_id(parsed.youtube_id)
        if parsed.spotify_id is not None:
            return self._repo.get_by_spotify_id(parsed.spotify_id)
        return None

    def _add_once(self, find: Callable[[], Song | None], stage: Callable[[], Song]) -> CreatedSong:
        """Alta idempotente: canción y trabajo se guardan en una sola transacción."""
        existing = find()
        if existing is not None:
            return CreatedSong(existing, created=False)
        try:
            song = stage()
            self._jobs.stage_job(song.id)
            self._session.commit()
        except IntegrityError:  # otra alta simultánea ganó la carrera
            self._session.rollback()
            existing = find()
            if existing is None:
                raise
            return CreatedSong(existing, created=False)
        except Exception:
            self._session.rollback()
            raise
        return CreatedSong(song, created=True)

    def _queued(self, song: Song) -> Song:
        self._jobs.add_job(song.id)
        return song

    def _entry(self, song: Song) -> SongEntry:
        active = self._repo.active_job(song.id)
        latest = self._repo.latest_job(song.id)
        return SongEntry(
            song,
            current_step=active.current_step if active else None,
            error=latest.error if latest else None,
        )
