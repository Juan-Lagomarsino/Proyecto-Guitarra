"""Paso de riffs (F5): pista de guitarra -> notas -> secciones candidatas -> eventos en beats.

Todavía NO digita ni envía a la API (eso es F5-T08). Salida: `{riffs: {section_id: [{midi, t,
dur, confidence}]}, skipped: motivo | None}`, con `t`/`dur` en beats relativos al inicio de la
sección. Sin basic-pitch el paso se saltea con un aviso: no falla el trabajo.
"""

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from guitarra_worker.adapters.transcriber import Transcriber, TranscriberUnavailable
from guitarra_worker.domain.quantize import BeatGrid, quantize_section
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


class RiffsStep:
    name = "riffs"
    version = "1"

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
