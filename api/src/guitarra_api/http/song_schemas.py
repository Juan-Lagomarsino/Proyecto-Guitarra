import datetime as dt
from typing import Any, Literal, Self
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from guitarra_api.http.audio_schemas import AudioAssetOut

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


class CifraIn(BaseModel):
    """Texto de la cifra pegado a mano (ADR 0012) y, opcional, el link de referencia."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=50000)
    url: str | None = Field(default=None, description="Link http(s) de la página de la cifra")

    @field_validator("url")
    @classmethod
    def _http_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("El link tiene que ser http o https")
        return value


class CifraSavedOut(SongSummaryOut):
    reanalysis_queued: bool = Field(
        description="false si ya había un análisis activo: la cifra se guardó igual"
    )


class SongSectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    start_s: float
    end_s: float
    position: int
    stale: bool = Field(
        default=False, description="Desapareció en un reanálisis pero conserva ejercicios"
    )


class SongDetailOut(SongSummaryOut):
    duration_s: float | None
    year: int | None
    has_cifra: bool
    cifra_url: str | None
    sections: list[SongSectionOut]
    audio: list[AudioAssetOut]
    separation_status: Literal["none", "queued", "running", "done", "error"]


class SongChartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    song_id: int
    instrument: Instrument
    version: int
    origin: Literal["auto", "cifraclub", "user"]
    confidence: float | None
    content: dict[str, Any] = Field(description="SongChartContent (schemas/song_chart.schema.json)")
    created_at: dt.datetime
    riff_sources: dict[str, Literal["auto", "usuario"] | None] = Field(
        default_factory=dict,
        description="De dónde viene el riff de cada sección (por id): la automática, la del "
        "usuario, o null si no tiene riff",
    )


class SectionExerciseIn(BaseModel):
    type: Literal["chords", "strumming", "riff"] = Field(
        description="Cambio de acordes, rasgueo o riff de la sección"
    )
    instrument: Instrument = Field(description="Chart de qué guitarra se usa de base")
