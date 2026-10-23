"""Reglas de recordatorio: días excluidos, umbral de inactividad y franja preferida."""

import re
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DEFAULT_INACTIVITY_THRESHOLD_DAYS = 3
MAX_INACTIVITY_THRESHOLD_DAYS = 365


class PreferredWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def _is_hhmm(cls, value: str) -> str:
        if not _HHMM.match(value):
            raise ValueError("Debe tener formato HH:MM (24 h)")
        return value

    @model_validator(mode="after")
    def _start_before_end(self) -> Self:
        if self.start >= self.end:
            raise ValueError("`start` debe ser anterior a `end`")
        return self


class ReminderRulesData(BaseModel):
    """Días 0-6 con 0 = lunes (como `date.weekday()`)."""

    model_config = ConfigDict(extra="forbid")

    excluded_weekdays: list[Annotated[int, Field(ge=0, le=6)]] = Field(default_factory=list)
    inactivity_threshold_days: int = Field(
        default=DEFAULT_INACTIVITY_THRESHOLD_DAYS, ge=1, le=MAX_INACTIVITY_THRESHOLD_DAYS
    )
    preferred_window: PreferredWindow | None = None

    @field_validator("excluded_weekdays")
    @classmethod
    def _unique_sorted(cls, value: list[int]) -> list[int]:
        return sorted(set(value))
