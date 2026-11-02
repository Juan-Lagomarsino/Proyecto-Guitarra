"""Paso 2b: convertir el original a `.m4a` (AAC) y subirlo a la API (ADR 0013).

Salida: `{kind, m4a_path, uploaded}`. `uploaded` es False si el mismo archivo ya se había subido
para esta canción (marcador en la caché de la canción: tamaño + hash + id de canción).

Fallos: si la subida falla, el paso falla (no se sigue a ciegas): un error de red o 5xx es
reintentable (la API reencola el trabajo y la caché evita reconvertir); un 4xx (tope de tamaño,
formato) es permanente porque reintentar daría lo mismo. Perder el lease sube tal cual.
"""

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from guitarra_worker.api_client import ApiError, Job
from guitarra_worker.pipeline.step import (
    PermanentStepError,
    PipelineContext,
    RetryableStepError,
)

M4A_NAME = "original.m4a"
UPLOAD_MARKER_NAME = "original.m4a.uploaded.json"
ASSET_KIND = "original"
HASH_CHUNK_BYTES = 1024 * 1024

Converter = Callable[[Path, Path], None]


class AssetUploader(Protocol):
    def upload_asset(self, job_id: int | str, kind: str, path: Path) -> None: ...


def _fingerprint(path: Path, song_id: int | str) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return {"song_id": str(song_id), "size": path.stat().st_size, "sha256": digest.hexdigest()}


def _already_uploaded(marker: Path, fingerprint: dict[str, Any]) -> bool:
    try:
        return json.loads(marker.read_text(encoding="utf-8")) == fingerprint
    except (OSError, ValueError):
        return False


class PublishAudioStep:
    name = "publish_audio"
    version = "1"

    def __init__(self, convert: Converter, uploader: AssetUploader) -> None:
        self._convert = convert
        self._uploader = uploader

    def cache_token(self, job: Job) -> str:
        """La subida es por canción: si se recrea con otro song_id hay que volver a subir."""
        return str(job.song_id)

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        wav_path = Path(ctx.outputs["download"]["wav_path"])
        m4a_path = ctx.song_dir / M4A_NAME
        if not m4a_path.exists() or m4a_path.stat().st_mtime < wav_path.stat().st_mtime:
            ctx.progress("Convirtiendo el audio a m4a")
            self._convert(wav_path, m4a_path)
        fingerprint = _fingerprint(m4a_path, ctx.job.song_id)
        marker = ctx.song_dir / UPLOAD_MARKER_NAME
        uploaded = not _already_uploaded(marker, fingerprint)
        if uploaded:
            ctx.progress("Subiendo el audio a la API")
            self._upload(ctx, m4a_path)
            marker.write_text(json.dumps(fingerprint), encoding="utf-8")
        return {"kind": ASSET_KIND, "m4a_path": str(m4a_path.resolve()), "uploaded": uploaded}

    def _upload(self, ctx: PipelineContext, m4a_path: Path) -> None:
        try:
            self._uploader.upload_asset(ctx.job.job_id, ASSET_KIND, m4a_path)
        except ApiError as exc:
            message = f"No pude subir el audio a la API: {exc}"
            if exc.status_code is not None and 400 <= exc.status_code < 500:
                raise PermanentStepError(
                    f"{message} (la API lo rechazó con {exc.status_code})"
                ) from exc
            raise RetryableStepError(message) from exc
