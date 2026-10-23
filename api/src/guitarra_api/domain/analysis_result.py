"""Resultado de un análisis que el worker entrega a la API (cuerpo de `POST /jobs/{id}/result`)."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from guitarra_api.domain.song_chart import SECTION_ID_PATTERN, SongChartContent


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SectionResult(_Strict):
    slug: Annotated[str, Field(pattern=SECTION_ID_PATTERN, max_length=80)]
    name: Annotated[str, Field(min_length=1, max_length=120)]
    start_s: Annotated[float, Field(ge=0)]
    end_s: float
    position: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def _start_is_before_end(self) -> Self:
        if self.start_s >= self.end_s:
            raise ValueError(f"sección '{self.slug}': 'start_s' debe ser menor que 'end_s'")
        return self


class SongMetadataResult(_Strict):
    """Metadatos que el análisis descubrió; los `None` no pisan lo que ya tiene la canción."""

    bpm: Annotated[float, Field(gt=0)] | None = None
    key: Annotated[str, Field(min_length=1, max_length=20)] | None = None
    duration_s: Annotated[float, Field(gt=0)] | None = None
    year: Annotated[int, Field(ge=1000, le=3000)] | None = None
    youtube_id: Annotated[str, Field(min_length=1, max_length=32)] | None = None
    title: Annotated[str, Field(min_length=1, max_length=300)] | None = None
    artist: Annotated[str, Field(min_length=1, max_length=300)] | None = None


class AnalysisResult(_Strict):
    metadata: SongMetadataResult = Field(default_factory=SongMetadataResult)
    sections: Annotated[list[SectionResult], Field(min_length=1)]
    charts: Annotated[list[SongChartContent], Field(min_length=1)]

    @model_validator(mode="after")
    def _sections_are_unique(self) -> Self:
        slugs = [section.slug for section in self.sections]
        positions = [section.position for section in self.sections]
        if len(set(slugs)) != len(slugs) or len(set(positions)) != len(positions):
            raise ValueError("las secciones no pueden repetir 'slug' ni 'position'")
        return self

    @model_validator(mode="after")
    def _one_chart_per_instrument(self) -> Self:
        instruments = [chart.instrument for chart in self.charts]
        if len(set(instruments)) != len(instruments):
            raise ValueError("hay más de un chart para el mismo instrumento")
        return self

    @model_validator(mode="after")
    def _charts_match_sections(self) -> Self:
        expected = {section.slug for section in self.sections}
        for chart in self.charts:
            if {section.id for section in chart.sections} != expected:
                raise ValueError(
                    f"las secciones del chart '{chart.instrument}' no coinciden con las del body"
                )
        return self
