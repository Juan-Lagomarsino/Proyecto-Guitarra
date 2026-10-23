"""Paso de estructura: secciones de la canción con tiempos, compases y nombres heurísticos.

Entrada (salidas previas): `download.wav_path` y `download.duration_s`, y `tempo.beats` /
`tempo.downbeats` (segundos). Salida: `{sections: [{order, start_s, end_s, start_bar, end_bar,
group, name}], confidence}`. Sin grilla de beats es "sin datos" (secciones vacías), no un error.
`name` es None cuando no hay repeticiones que lo justifiquen; T13 pisa los nombres con los de
Cifra Club.

Mapeo a `ChartSection` (api/.../domain/song_chart.py), a cargo de T13:
- `name` None: T13 pone uno por defecto a partir de `group` (p. ej. "Parte A").
- `id`: lo genera T13.
- `confidence` "baja" / "media" pasa a número: baja = 0.3, media = 0.6 (propuesta).
- `order`, `start_s` y `end_s` van tal cual; `start_bar`, `end_bar` y `group` no van al chart.
"""

import logging
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from guitarra_worker.domain.structure import analyze_structure
from guitarra_worker.pipeline.step import PipelineContext
from guitarra_worker.steps.tempo import BEATS_KEY, DOWNBEATS_KEY, TempoStep

logger = logging.getLogger(__name__)

TEMPO_STEP = TempoStep.name
NO_DATA = {"sections": [], "confidence": "baja"}


class SelfSimilarityProvider(Protocol):
    def self_similarity(self, wav_path: Path, beats: np.ndarray) -> np.ndarray:
        """Matriz de autosimilitud (beats x beats) del audio."""
        ...


class StructureStep:
    name = "structure"
    version = "1"

    def __init__(self, similarity: SelfSimilarityProvider) -> None:
        self._similarity = similarity

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        tempo = ctx.outputs.get(TEMPO_STEP)
        if tempo is None:
            logger.warning("Estructura: no hay salida del paso '%s'; sin secciones", TEMPO_STEP)
            return dict(NO_DATA)
        beats = np.asarray(tempo.get(BEATS_KEY) or [], dtype=float)
        downbeats = np.asarray(tempo.get(DOWNBEATS_KEY) or [], dtype=float)
        if len(beats) == 0 or len(downbeats) == 0:
            logger.info("Estructura: el tempo no trae beats o downbeats; sin secciones")
            return dict(NO_DATA)
        download = ctx.outputs["download"]
        ctx.progress("Analizando estructura")
        ssm = self._similarity.self_similarity(Path(download["wav_path"]), beats)
        result = analyze_structure(ssm, beats, downbeats, float(download["duration_s"]))
        return {
            "sections": [section.to_dict() for section in result.sections],
            "confidence": result.confidence,
        }
