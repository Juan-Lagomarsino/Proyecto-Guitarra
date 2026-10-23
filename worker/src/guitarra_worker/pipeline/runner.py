"""Ejecuta los pasos en orden, con caché en disco por paso y heartbeat."""

import hashlib
import json
import logging
import os
import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from guitarra_worker.api_client import ApiError, Job, LeaseLostError
from guitarra_worker.pipeline.step import PipelineContext, Step, cache_key

log = logging.getLogger(__name__)

HeartbeatFn = Callable[[str | None], None]
AssembleFn = Callable[[dict[str, dict[str, Any]]], dict[str, Any]]


def chain_key(previous_key: str, step: Step) -> str:
    """Clave de caché de un paso: combina su versión con las de todos los pasos previos."""
    raw = f"{previous_key}|{step.name}|{step.version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def read_step_cache(path: Path, version: str) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("version") != version:
        return None
    output = data.get("output")
    return output if isinstance(output, dict) else None


def write_step_cache(path: Path, version: str, output: dict[str, Any]) -> None:
    """Escritura atómica: archivo temporal en la misma carpeta y rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"version": version, "output": output}), encoding="utf-8")
    os.replace(tmp, path)


class Heartbeat:
    """Manda heartbeats con el paso actual: uno al empezar cada paso y otros en un hilo."""

    def __init__(self, send: HeartbeatFn, interval_s: float) -> None:
        self._send = send
        self._interval_s = interval_s
        self._step: str | None = None
        self._lost = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def __enter__(self) -> "Heartbeat":
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def beat(self, step: str | None) -> None:
        """Heartbeat inmediato. Lanza LeaseLostError si el trabajo ya no es nuestro."""
        self._step = step
        self.check()
        self._send_or_mark_lost()
        self.check()

    def check(self) -> None:
        if self._lost.is_set():
            raise LeaseLostError("Se perdió el lease del trabajo")

    def _send_or_mark_lost(self) -> None:
        try:
            self._send(self._step)
        except LeaseLostError:
            self._lost.set()

    def _loop(self) -> None:
        while not self._stop.wait(self._interval_s):
            try:
                self._send_or_mark_lost()
            except ApiError as exc:
                log.warning("Heartbeat falló, sigo: %s", exc)
            if self._lost.is_set():
                return


def run_pipeline(
    steps: Sequence[Step],
    job: Job,
    cache_dir: Path,
    heartbeat: Heartbeat,
    assemble: AssembleFn,
) -> dict[str, Any]:
    """Corre los pasos y devuelve `assemble(outputs)`: el cuerpo del result para la API.

    La caché de cada paso se invalida si cambia su versión o la de cualquier paso anterior.

    Lanza LeaseLostError si se pierde el lease; cualquier otra excepción del paso sube tal cual
    (RetryableStepError incluida) para que el loop decida el `fail`.
    """
    song_dir = cache_dir / cache_key(job)

    def on_progress(message: str) -> None:
        log.info("[%s] %s", job.job_id, message)
        heartbeat.check()

    ctx = PipelineContext(job=job, song_dir=song_dir, progress=on_progress)
    key = ""
    for step in steps:
        heartbeat.beat(step.name)
        key = chain_key(key, step)
        cache_path = song_dir / "steps" / f"{step.name}.json"
        output = read_step_cache(cache_path, key)
        if output is None:
            log.info("Paso %s: ejecutando", step.name)
            output = step.run(ctx)
            write_step_cache(cache_path, key, output)
        else:
            log.info("Paso %s: reusa caché", step.name)
        ctx.outputs[step.name] = output
    heartbeat.check()
    return assemble(ctx.outputs)
