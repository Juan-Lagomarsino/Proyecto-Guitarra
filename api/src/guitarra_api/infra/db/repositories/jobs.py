import datetime as dt

from sqlalchemy import and_, case, or_, select
from sqlalchemy.orm import Session

from guitarra_api.infra.db.models import AnalysisJob, Song

ANALYZE_JOB = "analyze"
SEPARATION_JOB = "separation"


class JobRepository:
    """Acceso a `analysis_jobs`. Solo `add_job` hace commit; el resto lo maneja el servicio."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def stage_job(self, song_id: int, max_attempts: int = 3) -> AnalysisJob:
        """Encola un análisis y deja la canción en `queued`, con flush y sin commit."""
        job = self.stage_typed_job(song_id, ANALYZE_JOB, max_attempts)
        song = self._session.get(Song, song_id)
        if song is not None:
            song.analysis_status = "queued"
        return job

    def stage_separation(self, song_id: int, max_attempts: int = 3) -> AnalysisJob:
        """Encola la separación de la canción; no toca su `analysis_status`."""
        return self.stage_typed_job(song_id, SEPARATION_JOB, max_attempts)

    def stage_typed_job(self, song_id: int, job_type: str, max_attempts: int) -> AnalysisJob:
        job = AnalysisJob(
            song_id=song_id, type=job_type, status="queued", max_attempts=max_attempts
        )
        self._session.add(job)
        self._session.flush()
        return job

    def add_job(self, song_id: int, max_attempts: int = 3) -> AnalysisJob:
        job = self.stage_job(song_id, max_attempts)
        self._session.commit()
        return job

    def get(self, job_id: int) -> AnalysisJob | None:
        return self._session.get(AnalysisJob, job_id)

    def lock_next_available(self, now: dt.datetime) -> AnalysisJob | None:
        """El más viejo en cola o con el lease vencido (análisis antes que separación)."""
        available = or_(
            AnalysisJob.status == "queued",
            and_(AnalysisJob.status == "running", AnalysisJob.lease_until < now),
        )
        analysis_first = case((AnalysisJob.type == ANALYZE_JOB, 0), else_=1)
        return self._session.scalar(
            select(AnalysisJob)
            .where(available)
            .order_by(analysis_first, AnalysisJob.created_at, AnalysisJob.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )

    def lock(self, job_id: int) -> AnalysisJob | None:
        """Bloquea el job (espera si otro lo tiene) y refresca su estado desde la base."""
        return self._session.scalar(
            select(AnalysisJob)
            .where(AnalysisJob.id == job_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
