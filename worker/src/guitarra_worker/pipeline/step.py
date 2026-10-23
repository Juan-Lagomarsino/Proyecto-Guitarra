"""Interfaz de los pasos del pipeline y su contexto."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from guitarra_worker.api_client import Job

ProgressCallback = Callable[[str], None]


class RetryableStepError(Exception):
    """Error transitorio (red, timeout): la API puede reencolar el trabajo."""


class PermanentStepError(Exception):
    """Error que reintentar no arregla (video privado, faltan credenciales, entrada inválida)."""


def _ignore_progress(message: str) -> None:
    return None


@dataclass
class PipelineContext:
    """Lo que ve cada paso.

    - job: datos del trabajo reclamado.
    - song_dir: carpeta de caché de la canción (por youtube_id; si no hay, por song_id).
      Los pasos pueden dejar ahí archivos grandes (audio, etc.); la salida JSON la guarda el runner.
    - outputs: salidas de los pasos anteriores, por nombre de paso.
    - progress: callback para avisar avance en pasos largos (loguea y aborta si se perdió el lease).
    """

    job: Job
    song_dir: Path
    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    progress: ProgressCallback = _ignore_progress


class Step(Protocol):
    name: str
    version: str

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        """Devuelve un dict serializable a JSON. 'Sin datos' es un resultado válido, no un error."""
        ...


def step_cache_token(step: Step, job: Job) -> str:
    """Dato del trabajo que cambia la salida del paso, aparte de la canción (opcional).

    Un paso lo declara con un método `cache_token(job) -> str`; si el token cambia, la caché del
    paso y la de los siguientes se invalidan. Vacío = el paso no depende de nada extra.
    """
    token = getattr(step, "cache_token", None)
    return token(job) if callable(token) else ""


def cache_key(job: Job) -> str:
    return job.youtube_id or f"song-{job.song_id}"
