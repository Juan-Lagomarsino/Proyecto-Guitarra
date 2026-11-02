"""Audio: el worker lo sube por `/jobs/{id}/assets/{kind}`; la UI lo baja con range requests."""

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from guitarra_api.config import Settings
from guitarra_api.http.audio_schemas import AudioKind, AudioUploadedOut
from guitarra_api.http.auth import get_api_settings, require_audio_token, require_worker_token
from guitarra_api.http.byte_range import ByteRange, UnsatisfiableRangeError, parse_range
from guitarra_api.infra.audio_store import AudioStore, AudioTooLargeError
from guitarra_api.infra.db.models import AudioAsset
from guitarra_api.infra.db.repositories.jobs import JobRepository
from guitarra_api.infra.db.session import get_session

CHUNK_BYTES = 64 * 1024
FORMAT_BY_CONTENT_TYPE = {"audio/mp4": "m4a", "audio/x-m4a": "m4a"}
CONTENT_TYPE_BY_FORMAT = {"m4a": "audio/mp4"}

upload_router = APIRouter(
    prefix="/jobs", tags=["jobs"], dependencies=[Depends(require_worker_token)]
)
download_router = APIRouter(tags=["canciones"], dependencies=[Depends(require_audio_token)])

Db = Annotated[Session, Depends(get_session)]
ApiSettings = Annotated[Settings, Depends(get_api_settings)]


def get_audio_store(settings: ApiSettings) -> AudioStore:
    return AudioStore(settings.guitar_audio_dir)


Store = Annotated[AudioStore, Depends(get_audio_store)]


@upload_router.post("/{job_id}/assets/{kind}", response_model=AudioUploadedOut)
async def upload_asset(
    job_id: int,
    kind: AudioKind,
    request: Request,
    session: Db,
    settings: ApiSettings,
    store: Store,
) -> AudioUploadedOut:
    """Cuerpo binario crudo (`Content-Type: audio/mp4`); reemplaza el audio previo del tipo."""
    audio_format = _format_of(request.headers.get("content-type", ""))
    job = JobRepository(session).get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No existe el trabajo {job_id}")
    max_bytes = settings.guitar_audio_max_bytes
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > max_bytes:
        raise _too_large(max_bytes)

    pending = store.begin(job.song_id, kind, audio_format, max_bytes)
    try:
        async for chunk in request.stream():
            pending.write(chunk)
        if pending.size == 0:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El cuerpo está vacío")
    except AudioTooLargeError as error:
        pending.abort()
        raise _too_large(max_bytes) from error
    except BaseException:
        pending.abort()
        raise
    stored = pending.commit()
    _register(session, store, job.song_id, kind, audio_format, stored.relative_path)
    return AudioUploadedOut(kind=kind, format=audio_format, size=stored.size)


@download_router.get(
    "/songs/{song_id}/audio/{kind}",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"audio/mp4": {}}},
        206: {"description": "Rango parcial"},
        416: {"description": "Rango no satisfacible"},
    },
)
def download_audio(
    song_id: int,
    kind: AudioKind,
    session: Db,
    store: Store,
    range_header: Annotated[str | None, Header(alias="Range")] = None,
):
    asset = session.scalar(
        select(AudioAsset).where(AudioAsset.song_id == song_id, AudioAsset.kind == kind)
    )
    path = store.resolve(asset.path) if asset else None
    if asset is None or path is None or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No hay audio de ese tipo para la canción")
    size = path.stat().st_size
    headers = {"Accept-Ranges": "bytes"}
    media_type = CONTENT_TYPE_BY_FORMAT.get(asset.format, "application/octet-stream")
    if range_header is None:
        window, status_code = ByteRange(0, size - 1), status.HTTP_200_OK
    else:
        try:
            window = parse_range(range_header, size)
        except UnsatisfiableRangeError:
            return Response(
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                headers={**headers, "Content-Range": f"bytes */{size}"},
            )
        status_code = status.HTTP_206_PARTIAL_CONTENT
        headers["Content-Range"] = f"bytes {window.start}-{window.end}/{size}"
    headers["Content-Length"] = str(window.length)
    return StreamingResponse(
        _read_window(path, window), status_code=status_code, media_type=media_type, headers=headers
    )


def _read_window(path: Path, window: ByteRange) -> Iterator[bytes]:
    remaining = window.length
    with path.open("rb") as file:
        file.seek(window.start)
        while remaining > 0:
            chunk = file.read(min(CHUNK_BYTES, remaining))
            if not chunk:
                return
            remaining -= len(chunk)
            yield chunk


def _format_of(content_type: str) -> str:
    media_type = content_type.split(";")[0].strip().lower()
    audio_format = FORMAT_BY_CONTENT_TYPE.get(media_type)
    if audio_format is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Formato no soportado: {media_type or 'sin Content-Type'} (usar audio/mp4)",
        )
    return audio_format


def _too_large(max_bytes: int) -> HTTPException:
    return HTTPException(
        status.HTTP_413_CONTENT_TOO_LARGE, f"El audio supera el tope de {max_bytes} bytes"
    )


def _register(
    session: Session, store: AudioStore, song_id: int, kind: str, audio_format: str, path: str
) -> None:
    asset = session.scalar(
        select(AudioAsset).where(AudioAsset.song_id == song_id, AudioAsset.kind == kind)
    )
    if asset is None:
        session.add(AudioAsset(song_id=song_id, kind=kind, path=path, format=audio_format))
    else:
        if asset.path != path:
            store.remove(asset.path)
        asset.path, asset.format = path, audio_format
    session.commit()
