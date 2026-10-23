"""Paso: tempo y compases con beat_this.

Entrada: `download.wav_path`. Salida: `{bpm, beats_per_bar, beats, downbeats, first_beat_s,
first_downbeat_s}` (tiempos en segundos; ver `domain/tempo.py`). Sin beats detectados el resultado
trae `bpm` y demás en None/vacío: "sin datos" no es un error.

Tests: la lógica va con tracker falso y corre siempre. El test con el modelo real (clicks sintéticos
a BPM conocido, +-1) corre solo en local con el extra `analysis` y los pesos instalados
(`scripts/install.ps1`); en la CI se omite.
"""

from pathlib import Path
from typing import Any, Protocol

from guitarra_worker.adapters.beat_this import BeatGrid
from guitarra_worker.domain.tempo import analyze_beats
from guitarra_worker.pipeline.step import PermanentStepError, PipelineContext

# Contrato con los pasos que consumen el tempo (acordes, estructura): estas claves no cambian.
BPM_KEY = "bpm"  # float
BEATS_KEY = "beats"  # segundos, ascendente
DOWNBEATS_KEY = "downbeats"  # segundos, subconjunto de beats: primer tiempo de cada compás


class BeatTracker(Protocol):
    def track(self, wav_path: Path) -> BeatGrid: ...


class TempoStep:
    name = "tempo"
    version = "1"

    def __init__(self, tracker: BeatTracker) -> None:
        self._tracker = tracker

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        wav_path = Path(ctx.outputs["download"]["wav_path"])
        if not wav_path.exists():
            raise PermanentStepError(f"No encuentro el audio para analizar el tempo: {wav_path}")
        ctx.progress("Detectando tempo y compases")
        grid = self._tracker.track(wav_path)
        return analyze_beats(grid.beats, grid.downbeats)
