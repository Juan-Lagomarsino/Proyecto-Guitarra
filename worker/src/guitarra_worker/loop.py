"""Loop principal: claim -> pipeline -> result/fail, con backoff si no hay trabajo."""

import logging
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from guitarra_worker.api_client import ApiClient, ApiError, Job, LeaseLostError
from guitarra_worker.config import Settings
from guitarra_worker.pipeline.runner import AssembleFn, Heartbeat, run_pipeline
from guitarra_worker.pipeline.step import PermanentStepError, RetryableStepError, Step

log = logging.getLogger(__name__)


def next_backoff(current_s: float, max_s: float) -> float:
    return min(current_s * 2, max_s)


def process_job(
    client: ApiClient,
    job: Job,
    steps: Sequence[Step],
    assemble: AssembleFn,
    cache_dir: Path,
    heartbeat_interval_s: float,
) -> bool:
    """Procesa un trabajo. Devuelve True si se envió resultado."""
    with Heartbeat(lambda step: client.heartbeat(job.job_id, step), heartbeat_interval_s) as hb:
        try:
            result = run_pipeline(steps, job, cache_dir, hb, assemble)
            client.send_result(job.job_id, result)
            return True
        except LeaseLostError:
            log.warning("Trabajo %s: lease perdido, se aborta", job.job_id)
        except (RetryableStepError, ApiError) as exc:  # ApiError: red caída, vale reintentar
            _report_failure(client, job, exc, retryable=True)
        except PermanentStepError as exc:  # no reintentable: se informa directo
            _report_failure(client, job, exc, retryable=False)
        except Exception as exc:  # noqa: BLE001 - cualquier fallo del paso se informa a la API
            _report_failure(client, job, exc, retryable=False)
    return False


def _report_failure(client: ApiClient, job: Job, exc: Exception, *, retryable: bool) -> None:
    log.error("Trabajo %s falló (retryable=%s): %s", job.job_id, retryable, exc, exc_info=exc)
    try:
        client.fail(job.job_id, f"{type(exc).__name__}: {exc}", retryable)
    except (LeaseLostError, ApiError) as report_error:
        log.error("No se pudo informar el fallo del trabajo %s: %s", job.job_id, report_error)


def run_loop(
    client: ApiClient,
    settings: Settings,
    steps: Sequence[Step],
    assemble: AssembleFn,
    *,
    once: bool = False,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    delay = settings.poll_interval_s
    while True:
        try:
            job = client.claim()
        except ApiError as exc:
            log.warning("No se pudo reclamar trabajo: %s", exc)
            job = None
        if job is not None:
            log.info("Trabajo %s reclamado (canción %s)", job.job_id, job.song_id)
            process_job(
                client, job, steps, assemble, settings.cache_dir, settings.heartbeat_interval_s
            )
            delay = settings.poll_interval_s
            if once:
                return
            continue
        if once:
            log.info("No hay trabajo")
            return
        sleep(delay)
        delay = next_backoff(delay, settings.max_backoff_s)
