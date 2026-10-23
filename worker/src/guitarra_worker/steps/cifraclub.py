"""Paso de Cifra Club: baja los acordes publicados. 'Sin datos' no es un error.

La alineación con lo detectado (domain/alignment.py) la hace el armado, que ve las
salidas de este paso y del de acordes.
"""

import logging
from typing import Any, Protocol

import httpx

from guitarra_worker.adapters.cifraclub import CifraClubChart, CifraClubClient
from guitarra_worker.config import Settings
from guitarra_worker.pipeline.step import PipelineContext

log = logging.getLogger(__name__)

NO_DATA: dict[str, Any] = {"found": False}


class ChartSource(Protocol):
    def fetch_chart(self, title: str | None, artist: str | None) -> CifraClubChart | None: ...


class CifraClubStep:
    name = "cifraclub"
    version = "1"

    def __init__(self, client: ChartSource) -> None:
        self._client = client

    @classmethod
    def from_settings(cls, settings: Settings) -> "CifraClubStep":
        client = CifraClubClient(
            httpx.Client(),
            base_url=settings.cifraclub_base_url,
            min_interval_s=settings.cifraclub_min_interval_s,
        )
        return cls(client)

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        try:
            chart = self._client.fetch_chart(ctx.job.title, ctx.job.artist)
        except Exception:
            log.exception("Cifra Club falló; sigo sin esos datos")
            return dict(NO_DATA)
        if chart is None:
            return dict(NO_DATA)
        return {
            "found": True,
            "url": chart.url,
            "key": chart.key,
            "capo": chart.capo,
            "sections": [{"name": s.name, "chords": s.chords} for s in chart.sections],
        }
