"""Cola de análisis: claim con lease, heartbeat, resultado y fallo. El worker no toca la base."""

import datetime as dt
from dataclasses import dataclass
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from guitarra_api.application.clock import Clock, utc_now
from guitarra_api.domain.analysis_result import AnalysisResult
from guitarra_api.infra.db.models import AnalysisJob, Exercise, Song, SongSection
from guitarra_api.infra.db.repositories.chord_preferences import ChordShapePreferenceRepository
from guitarra_api.infra.db.repositories.jobs import ANALYZE_JOB, SEPARATION_JOB, JobRepository
from guitarra_api.infra.db.repositories.songs import SongRepository

AUTO_ORIGIN = "auto"
NO_GUITAR_KIND = "no_guitar"


class JobNotFound(Exception):
    pass


class JobNotOwned(Exception):
    """El job no está `running` o lo tiene otro worker."""


class ResultTypeMismatch(Exception):
    """El cuerpo del resultado no corresponde al tipo del trabajo."""


class YoutubeIdConflict(Exception):
    """La búsqueda resolvió a un video que ya pertenece a otra canción."""


@dataclass(frozen=True)
class ClaimedJob:
    job_id: int
    job_type: str
    song_id: int
    title: str | None
    artist: str | None
    source: str
    url: str | None
    youtube_id: str | None
    spotify_id: str | None
    cifra_text: str | None
    attempt: int
    max_attempts: int
    lease_until: dt.datetime
    chord_shape_preferences: dict[str, Any]


class JobQueue:
    def __init__(self, session: Session, lease_seconds: int, clock: Clock = utc_now) -> None:
        self._session = session
        self._jobs = JobRepository(session)
        self._songs = SongRepository(session)
        self._chord_preferences = ChordShapePreferenceRepository(session)
        self._lease = dt.timedelta(seconds=lease_seconds)
        self._clock = clock

    def claim(self, worker_id: str) -> ClaimedJob | None:
        now = self._clock()
        while (job := self._jobs.lock_next_available(now)) is not None:
            song = self._require_song(job.song_id)
            if job.attempts >= job.max_attempts:
                self._give_up(job, song, "Se agotaron los intentos (lease vencido)", now)
                self._session.commit()
                continue
            job.status = "running"
            job.attempts += 1
            job.claimed_by = worker_id
            job.lease_until = now + self._lease
            job.current_step = None
            job.error = None
            if job.type == ANALYZE_JOB:
                song.analysis_status = "processing"
            self._session.commit()
            return self._claimed(job, song, self._chord_preferences.load().to_json())
        self._session.rollback()
        return None

    def heartbeat(self, job_id: int, worker_id: str, current_step: str | None) -> AnalysisJob:
        job = self._lock_owned(job_id, worker_id)
        job.lease_until = self._clock() + self._lease
        job.current_step = current_step
        self._session.commit()
        return job

    def complete(self, job_id: int, worker_id: str, result: AnalysisResult | None) -> AnalysisJob:
        """`result` es el análisis, o `None` para un trabajo de separación (sin chart)."""
        job = self._lock_owned(job_id, worker_id)
        if (job.type == ANALYZE_JOB) != (result is not None):
            self._session.rollback()
            raise ResultTypeMismatch(f"El cuerpo no corresponde a un trabajo '{job.type}'")
        try:
            song = self._require_song(job.song_id)
            if result is not None:
                self._store_analysis(song, result)
                self._enqueue_separation_if_needed(song)
            job.status = "done"
            job.error = None
            job.finished_at = self._clock()
            job.lease_until = None
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            if "youtube_id" in str(error.orig):
                raise YoutubeIdConflict("youtube_id ya pertenece a otra canción") from error
            raise
        except Exception:
            self._session.rollback()
            raise
        return job

    def _store_analysis(self, song: Song, result: AnalysisResult) -> None:
        self._apply_metadata(song, result)
        self._sync_sections(song, result)
        for chart in result.charts:
            self._songs.stage_chart(song.id, AUTO_ORIGIN, chart)
        song.analysis_status = "ready"

    def _enqueue_separation_if_needed(self, song: Song) -> None:
        if self._songs.has_audio_asset(song.id, NO_GUITAR_KIND):
            return
        if self._songs.active_job(song.id, SEPARATION_JOB) is not None:
            return
        self._jobs.stage_separation(song.id)

    def fail(self, job_id: int, worker_id: str, error: str, retryable: bool) -> AnalysisJob:
        job = self._lock_owned(job_id, worker_id)
        song = self._require_song(job.song_id)
        if retryable and job.attempts < job.max_attempts:
            job.status = "queued"
            job.error = error
            job.claimed_by = None
            job.lease_until = None
            job.current_step = None
            if job.type == ANALYZE_JOB:
                song.analysis_status = "queued"
        else:
            self._give_up(job, song, error, self._clock())
        self._session.commit()
        return job

    def _lock_owned(self, job_id: int, worker_id: str) -> AnalysisJob:
        job = self._jobs.lock(job_id)
        if job is None:
            self._session.rollback()
            raise JobNotFound(f"No existe el trabajo {job_id}")
        if job.status != "running" or job.claimed_by != worker_id:
            self._session.rollback()
            raise JobNotOwned(f"El trabajo {job_id} no está en curso para '{worker_id}'")
        return job

    def _require_song(self, song_id: int) -> Song:
        song = self._songs.get(song_id)
        if song is None:  # imposible por la FK con cascade; defensa ante datos inconsistentes
            raise JobNotFound(f"No existe la canción {song_id}")
        return song

    @staticmethod
    def _give_up(job: AnalysisJob, song: Song, error: str, now: dt.datetime) -> None:
        job.status = "error"
        job.error = error
        job.finished_at = now
        job.lease_until = None
        if job.type == ANALYZE_JOB:
            song.analysis_status = "error"

    def _apply_metadata(self, song: Song, result: AnalysisResult) -> None:
        metadata = result.metadata
        if metadata.youtube_id and metadata.youtube_id != song.youtube_id:
            owner = self._songs.get_by_youtube_id(metadata.youtube_id)
            if owner is not None and owner.id != song.id:
                raise YoutubeIdConflict(
                    f"El video {metadata.youtube_id} ya pertenece a la canción {owner.id}"
                )
        for field, value in metadata.model_dump(exclude_none=True).items():
            setattr(song, field, value)

    def _sync_sections(self, song: Song, result: AnalysisResult) -> None:
        """Upsert por (song_id, slug); las que desaparecen se borran salvo que tengan ejercicios."""
        existing = {s.slug: s for s in self._session.scalars(
            select(SongSection).where(SongSection.song_id == song.id)
        )}  # fmt: skip
        incoming = {s.slug for s in result.sections}
        for slug, section in existing.items():
            if slug not in incoming:
                self._retire(section)
        self._session.flush()
        # Las posiciones son únicas por canción: se liberan antes de reasignarlas.
        for section in existing.values():
            if section.slug in incoming:
                section.position = -section.id
        self._session.flush()
        for data in result.sections:
            section = existing.get(data.slug)
            if section is None:
                self._session.add(SongSection(song_id=song.id, **data.model_dump()))
            else:
                for field, value in data.model_dump().items():
                    setattr(section, field, value)
                section.stale = False
        self._session.flush()
        self._session.expire(song, ["sections"])

    def _retire(self, section: SongSection) -> None:
        in_use = self._session.scalar(
            select(exists().where(Exercise.song_section_id == section.id))
        )
        if in_use:
            section.stale = True
            section.position = -section.id  # libera la posición para las secciones nuevas
        else:
            self._session.delete(section)

    @staticmethod
    def _claimed(
        job: AnalysisJob, song: Song, chord_shape_preferences: dict[str, Any]
    ) -> ClaimedJob:
        assert job.lease_until is not None
        return ClaimedJob(
            job_id=job.id,
            job_type=job.type,
            song_id=song.id,
            title=song.title,
            artist=song.artist,
            source=song.source,
            url=song.url,
            youtube_id=song.youtube_id,
            spotify_id=song.spotify_id,
            cifra_text=song.cifra_text,
            attempt=job.attempts,
            max_attempts=job.max_attempts,
            lease_until=job.lease_until,
            chord_shape_preferences=chord_shape_preferences,
        )
