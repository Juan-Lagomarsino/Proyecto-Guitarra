from guitarra_core.chord_preferences import ChordShapePreferences
from sqlalchemy import select
from sqlalchemy.orm import Session

from guitarra_api.infra.db.models import ChordShapePreference


class ChordShapePreferenceRepository:
    """Acceso a `chord_shape_preferences`; no hace commit (lo hace el servicio)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def load(self) -> ChordShapePreferences:
        rows = self._session.scalars(select(ChordShapePreference)).all()
        return ChordShapePreferences.from_json({row.instrument: row.weights for row in rows})

    def stage_instrument(self, instrument: str, preferences: ChordShapePreferences) -> None:
        weights = preferences.to_json().get(instrument, {})
        row = self._session.get(ChordShapePreference, instrument)
        if row is None:
            self._session.add(ChordShapePreference(instrument=instrument, weights=weights))
        else:
            row.weights = weights
        self._session.flush()
