import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from guitarra_api.application.clock import Clock
from guitarra_api.application.progress_service import InvalidRangeError, ProgressService
from guitarra_api.http.auth import require_token
from guitarra_api.http.clock import get_clock
from guitarra_api.http.progress_schemas import CalendarDayOut, CalendarOut, SummaryOut
from guitarra_api.infra.db.session import get_session

router = APIRouter(dependencies=[Depends(require_token)], tags=["progreso"])


def get_progress_service(
    session: Annotated[Session, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ProgressService:
    return ProgressService(session, clock)


Service = Annotated[ProgressService, Depends(get_progress_service)]


@router.get("/progress/summary", response_model=SummaryOut)
def summary(service: Service):
    return service.summary()


@router.get("/progress/calendar", response_model=CalendarOut)
def calendar(
    service: Service,
    from_date: Annotated[dt.date, Query(alias="from")],
    to_date: Annotated[dt.date, Query(alias="to")],
):
    try:
        days = service.calendar(from_date, to_date)
    except InvalidRangeError as error:
        raise HTTPException(422, detail=str(error)) from error
    return CalendarOut(days=[CalendarDayOut(date=day, count=count) for day, count in days])
