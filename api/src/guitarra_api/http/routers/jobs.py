from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from guitarra_api.application.clock import Clock
from guitarra_api.application.job_queue import (
    JobNotFound,
    JobNotOwned,
    JobQueue,
    YoutubeIdConflict,
)
from guitarra_api.config import Settings
from guitarra_api.http.auth import get_api_settings, require_worker_token
from guitarra_api.http.clock import get_clock
from guitarra_api.http.job_schemas import (
    ClaimedJobOut,
    ClaimRequest,
    FailRequest,
    HeartbeatOut,
    HeartbeatRequest,
    JobStatusOut,
    ResultRequest,
)
from guitarra_api.infra.db.session import get_session

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(require_worker_token)])


def get_job_queue(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_api_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> JobQueue:
    return JobQueue(session, settings.guitar_job_lease_seconds, clock)


Queue = Annotated[JobQueue, Depends(get_job_queue)]


@router.post(
    "/claim",
    response_model=ClaimedJobOut,
    responses={
        status.HTTP_200_OK: {"model": ClaimedJobOut},
        status.HTTP_204_NO_CONTENT: {"description": "No hay trabajos disponibles"},
    },
)
def claim_job(body: ClaimRequest, queue: Queue) -> Any:
    job = queue.claim(body.worker_id)
    if job is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return ClaimedJobOut(**vars(job))


@router.post("/{job_id}/heartbeat")
def heartbeat(job_id: int, body: HeartbeatRequest, queue: Queue) -> HeartbeatOut:
    job = _guard(queue.heartbeat, job_id, body.worker_id, body.current_step)
    assert job.lease_until is not None
    return HeartbeatOut(job_id=job.id, status=job.status, lease_until=job.lease_until)


@router.post("/{job_id}/result")
def submit_result(job_id: int, body: ResultRequest, queue: Queue) -> JobStatusOut:
    job = _guard(queue.complete, job_id, body.worker_id, body)
    return JobStatusOut(job_id=job.id, status=job.status)


@router.post("/{job_id}/fail")
def fail_job(job_id: int, body: FailRequest, queue: Queue) -> JobStatusOut:
    job = _guard(queue.fail, job_id, body.worker_id, body.error, body.retryable)
    return JobStatusOut(job_id=job.id, status=job.status)


def _guard[T](operation: Callable[..., T], *args: Any) -> T:
    """Traduce los errores de la cola a HTTP."""
    try:
        return operation(*args)
    except JobNotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except (JobNotOwned, YoutubeIdConflict) as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
