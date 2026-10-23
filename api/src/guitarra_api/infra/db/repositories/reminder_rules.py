from sqlalchemy.orm import Session

from guitarra_api.domain.reminder_rules import PreferredWindow, ReminderRulesData
from guitarra_api.infra.db.models import ReminderRules

RULES_ID = 1


class ReminderRulesRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> ReminderRulesData:
        """Las reglas guardadas, o los defaults si todavía no hay fila (no la crea)."""
        row = self._session.get(ReminderRules, RULES_ID)
        if row is None:
            return ReminderRulesData()
        window = PreferredWindow(**row.preferred_window) if row.preferred_window else None
        return ReminderRulesData(
            excluded_weekdays=list(row.excluded_weekdays),
            inactivity_threshold_days=row.inactivity_threshold_days,
            preferred_window=window,
        )

    def save(self, rules: ReminderRulesData) -> ReminderRulesData:
        row = self._session.get(ReminderRules, RULES_ID) or ReminderRules(id=RULES_ID)
        row.excluded_weekdays = list(rules.excluded_weekdays)
        row.inactivity_threshold_days = rules.inactivity_threshold_days
        row.preferred_window = (
            rules.preferred_window.model_dump() if rules.preferred_window else None
        )
        self._session.add(row)
        self._session.commit()
        return rules
