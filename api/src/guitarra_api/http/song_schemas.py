import datetime as dt
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Instrument = Literal["classical", "electric"]


class SongIn(BaseModel):
    """Alta por link (`url`) o por nombre (`title` y `artist`); exactamente uno de los dos modos."""

    url: str | None = Field(default=None, description="Link de YouTube o de un tema de Spotify")
    title: str | None = Field(default=None, description="Título, para el alta por nombre")
    artist: str | None = Field(default=None, description="Artista, para el alta por nombre")

    @field_validator("url", "title", "artist")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def _exactly_one_mode(self) -> Self:
        by_name = bool(self.title) and bool(self.artist)
        partial_name = (self.title is not None or self.artist is not None) and not by_name
        by_url = bool(self.url)
        if partial_name or by_url == by_name:
            raise ValueError("Mandá `url`, o bien `title` y `artist` (no vacíos), pero no ambos")
        return self


class SongSummaryOut(BaseModel):
    id: int
    title: str | None = Field(description="null hasta que el worker lo completa")
    artist: str | None = Field(description="null hasta que el worker lo completa")
    source: Literal["youtube", "spotify", "search"]
    analysis_status: Literal["queued", "processing", "ready", "error"]
    current_step: str | None = Field(description="Paso del análisis activo; null si no hay")
    bpm: float | None
    key: str | None
    created_at: dt.datetime
    url: str | None
    error: str | None = Field(description="Error del último trabajo de análisis, si falló")


class SongSectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    start_s: float
    end_s: float
    position: int


class SongDetailOut(SongSummaryOut):
    duration_s: float | None
    year: int | None
    sections: list[SongSectionOut]


class SongChartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    song_id: int
    instrument: Instrument
    version: int
    origin: Literal["auto", "cifraclub", "user"]
    confidence: float | None
    content: dict[str, Any] = Field(description="SongChartContent (schemas/song_chart.schema.json)")
    created_at: dt.datetime
