import datetime as dt
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from guitarra_api.domain.analysis_result import AnalysisResult

WorkerId = Annotated[str, Field(min_length=1, max_length=120)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClaimRequest(_Strict):
    worker_id: WorkerId


class ClaimSectionOut(BaseModel):
    id: str
    name: str
    start_s: float
    end_s: float


class ClaimBeatGridOut(BaseModel):
    beats_s: list[float]
    downbeats_s: list[float]


class ClaimChartOut(BaseModel):
    """Estructura del chart auto vigente, para que la separación transcriba riffs por sección."""

    bpm: float
    time_signature: str
    capo: int
    beat_grid: ClaimBeatGridOut | None
    sections: list[ClaimSectionOut]


class ClaimedJobOut(BaseModel):
    job_id: int
    job_type: Literal["analyze", "separation"]
    song_id: int
    title: str | None
    artist: str | None
    source: str
    url: str | None
    youtube_id: str | None
    spotify_id: str | None
    cifra_text: str | None
    attempt: int
    max_attempts: int
    lease_until: dt.datetime
    # {instrumento: {acorde: {forma: peso}}}; la forma son 6 trastes absolutos (core)
    chord_shape_preferences: dict[str, Any] = Field(default_factory=dict)
    chart: ClaimChartOut | None = None


class HeartbeatRequest(_Strict):
    worker_id: WorkerId
    current_step: Annotated[str, Field(max_length=60)] | None = None


class HeartbeatOut(BaseModel):
    job_id: int
    status: str
    lease_until: dt.datetime


class ResultRequest(AnalysisResult):
    worker_id: WorkerId


class SeparationResultRequest(_Strict):
    """Resultado de una separación: los audios ya se subieron por `assets`, no hay chart."""

    worker_id: WorkerId
    riffs: dict[str, Any] | None = Field(
        default=None,
        description="Riffs por id de sección (Notation con el bpm del chart). Se validan uno "
        "por uno: los inválidos o de secciones inexistentes se descartan sin fallar el resto.",
    )


class FailRequest(_Strict):
    worker_id: WorkerId
    error: Annotated[str, Field(min_length=1, max_length=4000)]
    retryable: bool = True


class JobStatusOut(BaseModel):
    job_id: int
    status: str
