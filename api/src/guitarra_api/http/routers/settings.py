from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from guitarra_api.domain.app_settings import AppSettings
from guitarra_api.http.auth import require_token
from guitarra_api.infra.db.repositories.settings import SettingsRepository
from guitarra_api.infra.db.session import get_session

router = APIRouter(dependencies=[Depends(require_token)])


def get_settings_repository(
    session: Annotated[Session, Depends(get_session)],
) -> SettingsRepository:
    return SettingsRepository(session)


Repository = Annotated[SettingsRepository, Depends(get_settings_repository)]


@router.get("/settings")
def read_settings(repository: Repository) -> AppSettings:
    return repository.get()


@router.put("/settings")
def update_settings(settings: AppSettings, repository: Repository) -> AppSettings:
    return repository.save(settings)
