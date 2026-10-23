from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from guitarra_api.application.clock import Clock
from guitarra_api.application.session_service import SessionService
from guitarra_api.http.auth import require_token
from guitarra_api.http.clock import get_clock
from guitarra_api.http.progress_schemas import TodaySessionOut
from guitarra_api.infra.db.session import get_session

router = APIRouter(dependencies=[Depends(require_token)], tags=["sesiones"])


def get_session_service(
    session: Annotated[Session, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> SessionService:
    return SessionService(session, clock)


Service = Annotated[SessionService, Depends(get_session_service)]


@router.get("/sessions/today", response_model=TodaySessionOut)
def today(service: Service):
    return service.today()


@router.post("/sessions/today/regenerate", response_model=TodaySessionOut)
def regenerate(service: Service):
    return service.regenerate()
