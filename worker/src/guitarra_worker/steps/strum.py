"""Paso de rasgueo y arpegio: un patrón del catálogo por canción.

Entrada (salida previa): `tempo.bpm` y `tempo.beats_per_bar`. Salida:
`{strum, arpeggio}`, cada uno `None` (sin datos: sin tempo o compás sin patrones) o
`{pattern_id, pattern, accent, beats_per_cycle, source, confidence}`. `source` es "ollama" o
"rules"; `confidence` es una propuesta (reglas 0.4, Ollama 0.6) que T13 copia al chart.

Un patrón para toda la canción: T13 lo aplica a cada sección (SectionStrum), y el arpegio solo
va al chart de clásica. Si Ollama no responde, usa las reglas: este paso nunca falla por el LLM.
"""

from typing import Any

from guitarra_worker.pipeline.step import PipelineContext
from guitarra_worker.steps.tempo import BPM_KEY, TempoStep
from guitarra_worker.strum.catalog import Pattern, load_catalog
from guitarra_worker.strum.ollama_chooser import SongContext
from guitarra_worker.strum.rules import candidate_patterns
from guitarra_worker.strum.selection import PatternChooser, Selection, select_pattern

TEMPO_STEP = TempoStep.name
BEATS_PER_BAR_KEY = "beats_per_bar"
CONFIDENCE = {"rules": 0.4, "ollama": 0.6}
NO_DATA: dict[str, Any] = {"strum": None, "arpeggio": None}


def _selection_to_dict(selection: Selection | None) -> dict[str, Any] | None:
    if selection is None:
        return None
    return {
        **selection.pattern.to_dict(),
        "source": selection.source,
        "confidence": CONFIDENCE[selection.source],
    }


class StrumStep:
    name = "strum"
    version = "1"

    def __init__(
        self, chooser: PatternChooser | None, catalog: list[Pattern] | None = None
    ) -> None:
        self._chooser = chooser
        self._catalog = catalog if catalog is not None else load_catalog()

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        tempo = ctx.outputs.get(TEMPO_STEP) or {}
        bpm, beats_per_bar = tempo.get(BPM_KEY), tempo.get(BEATS_PER_BAR_KEY)
        if not bpm or not beats_per_bar:
            return dict(NO_DATA)
        ctx.progress("Eligiendo rasgueo y arpegio")
        song = SongContext(ctx.job.title, ctx.job.artist, float(bpm), int(beats_per_bar))
        return {
            "strum": self._select("strum", song),
            "arpeggio": self._select("arpeggio", song),
        }

    def _select(self, kind: str, song: SongContext) -> dict[str, Any] | None:
        candidates = candidate_patterns(self._catalog, kind, song.beats_per_bar, song.bpm)
        return _selection_to_dict(select_pattern(candidates, song, self._chooser))
