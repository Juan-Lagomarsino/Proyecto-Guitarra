"""Casos de uso de la biblioteca de canciones (Explorar)."""

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from guitarra_api.domain.song_source import ParsedSongUrl, parse_song_url
from guitarra_api.infra.db.models import Song, SongChart
from guitarra_api.infra.db.repositories.jobs import JobRepository
from guitarra_api.infra.db.repositories.songs import SongRepository


class SongNotFoundError(Exception):
    def __init__(self, song_id: int) -> None:
        super().__init__(f"Canción {song_id} no existe")


class ChartNotFoundError(Exception):
    def __init__(self, song_id: int, instrument: str) -> None:
        super().__init__(f"La canción {song_id} todavía no tiene chart para {instrument}")


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

    def reanalyze(self, song_id: int) -> Song:
        song = self._get(song_id)
        if self._repo.active_job(song_id) is not None:
            raise AnalysisAlreadyActiveError(song_id)
        return self._queued(song)

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
