"""Paso de riffs (F5): pista de guitarra -> notas -> secciones candidatas -> eventos en beats.

`BuildRiffsStep` digita y arma la notación (F5-T08). Salida de `RiffsStep`:
`{riffs: {section_id: [{midi, t, dur, confidence}]}, skipped: motivo | None}`, con `t`/`dur`
en beats relativos al inicio de la sección. Sin basic-pitch el paso se saltea con un aviso:
no falla el trabajo.
"""

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from guitarra_core.fingering import FingeringPreferences

from guitarra_worker.adapters.transcriber import Transcriber, TranscriberUnavailable
from guitarra_worker.api_client import Job
from guitarra_worker.domain.quantize import BeatGrid, quantize_section
from guitarra_worker.domain.riff_assembly import RiffChart, build_riffs
from guitarra_worker.domain.riff_candidates import SectionSpan, choose_candidates
from guitarra_worker.pipeline.step import PipelineContext

GUITAR_STEM = "guitar"


@dataclass(frozen=True)
class ChartInfo:
    """Lo que el paso necesita del chart: secciones y grilla (ver nota de contrato en el README)."""

    sections: Sequence[SectionSpan]
    grid: BeatGrid


def transcribe_section_riffs(
    transcriber: Transcriber,
    guitar_wav: Path,
    sections: Sequence[SectionSpan],
    grid: BeatGrid,
) -> dict[str, list[dict[str, Any]]]:
    """`{section_id: [eventos cuantizados]}` solo de las secciones candidatas y con notas."""
    notes = transcriber.transcribe(guitar_wav)
    by_id = {s.id: s for s in sections}
    riffs: dict[str, list[dict[str, Any]]] = {}
    for section_id in choose_candidates(sections, notes):
        section = by_id[section_id]
        events = quantize_section(notes, section.start_s, section.end_s, grid)
        if events:
            riffs[section_id] = [asdict(e) for e in events]
    return riffs


def _digest(data: object) -> str:
    raw = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def chart_info_of(ctx: PipelineContext) -> ChartInfo | None:
    """Secciones y grilla del chart del claim; sin chart o sin secciones, None."""
    chart = ctx.job.chart
    if chart is None or not chart.sections:
        return None
    beats = chart.beat_grid.beats_s if chart.beat_grid else []
    sections = [SectionSpan(s.id, s.name, s.start_s, s.end_s) for s in chart.sections]
    return ChartInfo(sections, BeatGrid(beats_s=beats, bpm=chart.bpm))


class RiffsStep:
    name = "riffs"
    version = "1"

    def cache_token(self, job: Job) -> str:
        """Las secciones y la grilla del chart cambian qué se transcribe y cómo se cuantiza."""
        return _digest(job.chart.model_dump()) if job.chart else ""

    def __init__(
        self, transcriber: Transcriber, chart_of: Callable[[PipelineContext], ChartInfo | None]
    ) -> None:
        self._transcriber = transcriber
        self._chart_of = chart_of

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        chart = self._chart_of(ctx)
        if chart is None:
            return {"riffs": {}, "skipped": "el trabajo no trae chart con secciones y grilla"}
        guitar = (ctx.outputs.get("separate") or {}).get("stems", {}).get(GUITAR_STEM)
        if not guitar or not Path(guitar).exists():
            return {"riffs": {}, "skipped": "no hay pista de guitarra separada"}
        ctx.progress("Transcribiendo la guitarra (riffs)")
        try:
            riffs = transcribe_section_riffs(
                self._transcriber, Path(guitar), chart.sections, chart.grid
            )
        except TranscriberUnavailable as exc:
            ctx.progress(f"Riffs salteados: {exc}")
            return {"riffs": {}, "skipped": str(exc)}
        return {"riffs": riffs, "skipped": None}


class BuildRiffsStep:
    """Digita los eventos de `riffs` (preferencias y capo) y arma la notación."""

    name = "build_riffs"
    version = "1"

    def cache_token(self, job: Job) -> str:
        return _digest(
            {
                "chart": job.chart.model_dump() if job.chart else None,
                "preferences": job.fingering_preferences,
            }
        )

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        chart = ctx.job.chart
        events = (ctx.outputs.get("riffs") or {}).get("riffs") or {}
        if chart is None or not events:
            return {"riffs": {}}
        preferences = FingeringPreferences.from_json(ctx.job.fingering_preferences)
        riff_chart = RiffChart(chart.bpm, chart.time_signature, chart.capo)
        return {"riffs": build_riffs(events, riff_chart, preferences)}
