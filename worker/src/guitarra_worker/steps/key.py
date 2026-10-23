"""Paso de tonalidad: Krumhansl-Schmuckler sobre el histograma de acordes del paso `chords`.

Salida: `{key: {tonic, mode, name, relative, confidence} | None}`. `None` (sin acordes o solo
silencio) es un resultado válido. La confianza tiene techo: esta técnica confunde relativas.
"""

from typing import Any

from guitarra_worker.domain.chords import ChordSpan
from guitarra_worker.domain.key import detect_key
from guitarra_worker.pipeline.step import PermanentStepError, PipelineContext

CONFIDENCE_DECIMALS = 3


class KeyStep:
    name = "key"
    version = "1"

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        chords = ctx.outputs.get("chords")
        if chords is None:
            raise PermanentStepError("Faltan los acordes: el paso «chords» tiene que correr antes")
        spans = [
            ChordSpan(c["start"], c["end"], c["label"], c["confidence"]) for c in chords["chords"]
        ]
        key = detect_key(spans)
        if key is None:
            return {"key": None}
        return {
            "key": {
                "tonic": key.tonic,
                "mode": key.mode,
                "name": key.name,
                "relative": key.relative,
                "confidence": round(key.confidence, CONFIDENCE_DECIMALS),
            }
        }
