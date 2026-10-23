import datetime as dt
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from guitarra_api.domain.analysis_result import AnalysisResult

WorkerId = Annotated[str, Field(min_length=1, max_length=120)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClaimRequest(_Strict):
    worker_id: WorkerId


class ClaimedJobOut(BaseModel):
    job_id: int
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


class HeartbeatRequest(_Strict):
    worker_id: WorkerId
    current_step: Annotated[str, Field(max_length=60)] | None = None


class HeartbeatOut(BaseModel):
    job_id: int
    status: str
    lease_until: dt.datetime


class ResultRequest(AnalysisResult):
    worker_id: WorkerId


class FailRequest(_Strict):
    worker_id: WorkerId
    error: Annotated[str, Field(min_length=1, max_length=4000)]
    retryable: bool = True


class JobStatusOut(BaseModel):
    job_id: int
    status: str
