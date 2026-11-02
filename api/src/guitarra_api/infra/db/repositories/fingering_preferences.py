from guitarra_core.fingering import FingeringPreferences
from sqlalchemy.orm import Session

from guitarra_api.infra.db.models import FingeringPreference

_ROW_ID = 1


class FingeringPreferenceRepository:
    """Acceso a `fingering_preferences` (fila única); no hace commit (lo hace el servicio)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def load(self) -> FingeringPreferences:
        row = self._session.get(FingeringPreference, _ROW_ID)
        return FingeringPreferences.from_json(row.weights if row else None)

    def stage(self, preferences: FingeringPreferences) -> None:
        weights = preferences.to_json()
        row = self._session.get(FingeringPreference, _ROW_ID)
        if row is None:
            self._session.add(FingeringPreference(id=_ROW_ID, weights=weights))
        else:
            row.weights = weights
        self._session.flush()
