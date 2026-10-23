from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from guitarra_api.domain.reminder_rules import ReminderRulesData
from guitarra_api.http.auth import require_token
from guitarra_api.infra.db.repositories.reminder_rules import ReminderRulesRepository
from guitarra_api.infra.db.session import get_session

router = APIRouter(dependencies=[Depends(require_token)], tags=["recordatorios"])


def get_rules_repository(
    session: Annotated[Session, Depends(get_session)],
) -> ReminderRulesRepository:
    return ReminderRulesRepository(session)


Repository = Annotated[ReminderRulesRepository, Depends(get_rules_repository)]


@router.get("/reminders/rules")
def read_rules(repository: Repository) -> ReminderRulesData:
    return repository.get()


@router.put("/reminders/rules")
def update_rules(rules: ReminderRulesData, repository: Repository) -> ReminderRulesData:
    return repository.save(rules)
