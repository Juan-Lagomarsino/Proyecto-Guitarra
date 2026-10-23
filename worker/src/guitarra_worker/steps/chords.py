"""Paso de acordes: reconoce acordes sobre la mezcla y los ajusta a la grilla de beats.

Entradas (salidas de pasos anteriores, por la caché encadenada del runner):
- `download`: `wav_path` y `duration_s`.
- `tempo`: `beats`, lista de tiempos de beat en segundos (T07).

Salida: `{model, chords: [{start, end, label, confidence}]}`. `label` es el nombre canónico del
core ("Am7", "G") o "N" sin acorde; `confidence` va de 0 a 1 (fracción del beat que cubría el
acorde). Sin beats (o sin paso tempo, con un warning) la lista queda vacía: es un resultado
válido y los pasos siguientes lo toleran.
"""

import logging
from pathlib import Path
from typing import Any, Protocol

from guitarra_worker.domain.chords import ChordSpan, RawChord, snap_to_beats
from guitarra_worker.pipeline.step import PipelineContext

log = logging.getLogger(__name__)

TIME_DECIMALS = 3


class ChordRecognizer(Protocol):
    name: str

    def recognize(self, wav_path: Path) -> list[RawChord]: ...


def _serialize(span: ChordSpan) -> dict[str, Any]:
    return {
        "start": round(span.start, TIME_DECIMALS),
        "end": round(span.end, TIME_DECIMALS),
        "label": span.label,
        "confidence": round(span.confidence, 3),
    }


class ChordsStep:
    name = "chords"
    version = "1"

    def __init__(self, recognizer: ChordRecognizer) -> None:
        self._recognizer = recognizer

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        beats = self._beats(ctx)
        model = self._recognizer.name
        if len(beats) < 2:
            return {"model": model, "chords": []}
        download = ctx.outputs["download"]
        ctx.progress("Reconociendo acordes")
        raw = self._recognizer.recognize(Path(download["wav_path"]))
        spans = snap_to_beats(raw, beats, download.get("duration_s"))
        return {"model": model, "chords": [_serialize(span) for span in spans]}

    @staticmethod
    def _beats(ctx: PipelineContext) -> list[float]:
        tempo = ctx.outputs.get("tempo")
        if tempo is None:
            log.warning("Falta la salida del paso «tempo»: acordes sin datos")
            return []
        return [float(b) for b in tempo.get("beats") or []]
