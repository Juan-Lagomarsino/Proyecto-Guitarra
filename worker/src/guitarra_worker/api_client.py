"""Adaptador HTTP hacia la API. Es el único módulo del worker que conoce las rutas."""

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import BaseModel

log = logging.getLogger(__name__)

MAX_ERROR_LENGTH = 4000  # límite del campo en la API


class LeaseLostError(Exception):
    """La API respondió 409: el trabajo ya no es de este worker."""


class ApiError(Exception):
    """Falla de red o respuesta inesperada de la API, después de los reintentos."""


class Job(BaseModel):
    job_id: int | str
    song_id: int | str
    title: str | None = None
    artist: str | None = None
    source: str | None = None
    url: str | None = None
    youtube_id: str | None = None
    spotify_id: str | None = None
    attempt: int = 1
    max_attempts: int | None = None
    lease_until: str | None = None


class ApiClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        worker_id: str,
        *,
        transport: httpx.BaseTransport | None = None,
        retries: int = 3,
        retry_delay_s: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._worker_id = worker_id
        self._retries = retries
        self._retry_delay_s = retry_delay_s
        self._sleep = sleep
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(30.0, connect=5.0),
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def claim(self) -> Job | None:
        response = self._post("/api/v1/jobs/claim", {"worker_id": self._worker_id})
        if response.status_code == 204:
            return None
        self._expect_ok(response)
        return Job.model_validate(response.json())

    def heartbeat(self, job_id: int | str, current_step: str | None) -> None:
        body = {"worker_id": self._worker_id, "current_step": current_step}
        self._post_job(job_id, "heartbeat", body)

    def send_result(self, job_id: int | str, result: dict[str, Any]) -> None:
        self._post_job(job_id, "result", {"worker_id": self._worker_id, **result})

    def fail(self, job_id: int | str, error: str, retryable: bool = True) -> None:
        body = {
            "worker_id": self._worker_id,
            "error": error[:MAX_ERROR_LENGTH],
            "retryable": retryable,
        }
        self._post_job(job_id, "fail", body)

    def _post_job(self, job_id: int | str, action: str, body: dict[str, Any]) -> None:
        response = self._post(f"/api/v1/jobs/{job_id}/{action}", body)
        if response.status_code == 409:
            raise LeaseLostError(f"El trabajo {job_id} ya no es de este worker")
        self._expect_ok(response)

    def _post(self, path: str, body: dict[str, Any]) -> httpx.Response:
        """POST con reintentos acotados ante errores de red y 5xx."""
        last_error: Exception | None = None
        for attempt in range(self._retries + 1):
            if attempt:
                self._sleep(self._retry_delay_s * 2 ** (attempt - 1))
            try:
                response = self._http.post(path, json=body)
            except httpx.TransportError as exc:
                last_error = exc
                log.warning("Error de red en %s (intento %d): %s", path, attempt + 1, exc)
                continue
            if response.status_code >= 500:
                last_error = ApiError(f"{path} respondió {response.status_code}")
                log.warning("%s (intento %d)", last_error, attempt + 1)
                continue
            return response
        raise ApiError(f"{path} falló tras {self._retries + 1} intentos: {last_error}")

    @staticmethod
    def _expect_ok(response: httpx.Response) -> None:
        if response.status_code >= 400:
            raise ApiError(f"{response.request.url.path} respondió {response.status_code}")
