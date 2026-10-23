from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from guitarra_api.application.song_service import (
    AnalysisAlreadyActiveError,
    ChartNotFoundError,
    SongDetail,
    SongEntry,
    SongNotFoundError,
    SongService,
)
from guitarra_api.domain.song_source import InvalidSongUrlError
from guitarra_api.http.auth import require_token
from guitarra_api.http.song_schemas import (
    Instrument,
    SongChartOut,
    SongDetailOut,
    SongIn,
    SongSummaryOut,
)
from guitarra_api.infra.db.models import Song
from guitarra_api.infra.db.session import get_session

router = APIRouter(dependencies=[Depends(require_token)], tags=["canciones"])


def get_song_service(session: Annotated[Session, Depends(get_session)]) -> SongService:
    return SongService(session)


Service = Annotated[SongService, Depends(get_song_service)]


def _summary(entry: SongEntry) -> SongSummaryOut:
    song = entry.song
    return SongSummaryOut(
        id=song.id,
        title=song.title,
        artist=song.artist,
        source=song.source,
        analysis_status=song.analysis_status,
        current_step=entry.current_step,
        bpm=song.bpm,
        key=song.key,
        created_at=song.created_at,
    )


def _detail(detail: SongDetail) -> SongDetailOut:
    song = detail.song
    return SongDetailOut(
        **_summary(detail).model_dump(),
        url=song.url,
        duration_s=song.duration_s,
        year=song.year,
        error=detail.error,
        sections=song.sections,
    )


def _summary_of(song: Song) -> SongSummaryOut:
    return _summary(SongEntry(song, current_step=None))


@router.post(
    "/songs",
    response_model=SongSummaryOut,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "La canción ya existía; no se encoló otro análisis"}},
)
def add_song(body: SongIn, response: Response, service: Service):
    try:
        result = (
            service.add_from_url(body.url)
            if body.url
            else service.add_from_name(body.title or "", body.artist or "")
        )
    except InvalidSongUrlError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return _summary_of(result.song)


@router.get("/songs", response_model=list[SongSummaryOut])
def list_songs(service: Service):
    return [_summary(entry) for entry in service.list_songs()]


@router.get("/songs/{song_id}", response_model=SongDetailOut)
def get_song(song_id: int, service: Service):
    try:
        return _detail(service.get_detail(song_id))
    except SongNotFoundError as error:
        raise _not_found(error) from error


@router.get("/songs/{song_id}/chart", response_model=SongChartOut)
def get_chart(song_id: int, instrument: Annotated[Instrument, Query()], service: Service):
    try:
        return service.current_chart(song_id, instrument)
    except (SongNotFoundError, ChartNotFoundError) as error:
        raise _not_found(error) from error


@router.post(
    "/songs/{song_id}/reanalyze",
    response_model=SongSummaryOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def reanalyze(song_id: int, service: Service):
    try:
        return _summary_of(service.reanalyze(song_id))
    except SongNotFoundError as error:
        raise _not_found(error) from error
    except AnalysisAlreadyActiveError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from error


def _not_found(error: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
