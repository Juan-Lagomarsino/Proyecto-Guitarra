from sqlalchemy.orm import Session

from guitarra_api.domain.app_settings import AppSettings, default_app_settings, settings_from_stored
from guitarra_api.infra.db.models import Settings

SETTINGS_ID = 1


class SettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> AppSettings:
        """Los ajustes guardados, o los defaults si todavía no hay fila (no la crea)."""
        row = self._session.get(Settings, SETTINGS_ID)
        if row is None:
            return default_app_settings()
        return settings_from_stored(
            timezone=row.timezone,
            theme_tokens=row.theme_tokens,
            fonts=row.fonts,
            default_instrument=row.default_instrument,
            tuning=row.tuning,
        )

    def save(self, settings: AppSettings) -> AppSettings:
        """Upsert de la fila única."""
        row = self._session.get(Settings, SETTINGS_ID) or Settings(id=SETTINGS_ID)
        row.timezone = settings.timezone
        row.theme_tokens = dict(settings.theme_tokens)
        row.fonts = dict(settings.fonts)
        row.default_instrument = settings.default_instrument
        row.tuning = list(settings.tuning)
        self._session.add(row)
        self._session.commit()
        return settings
