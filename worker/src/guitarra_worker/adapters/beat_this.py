"""Adaptador de beat_this: beats y downbeats de un WAV (CPU). Importa torch recién al usarse."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from guitarra_worker.adapters.beat_this_weights import is_valid_checkpoint
from guitarra_worker.pipeline.step import PermanentStepError


@dataclass(frozen=True)
class BeatGrid:
    beats: tuple[float, ...]
    downbeats: tuple[float, ...]


class BeatThisTracker:
    """Carga el modelo una sola vez y lo reusa entre canciones."""

    def __init__(self, checkpoint: Path, sha256: str, device: str = "cpu") -> None:
        self._checkpoint = checkpoint
        self._sha256 = sha256
        self._device = device
        self._model: Any = None

    def _load(self) -> Any:
        if not self._checkpoint.exists():
            raise PermanentStepError(
                f"Faltan los pesos de beat_this en {self._checkpoint}: corré scripts/install.ps1 "
                "o poné GUITAR_BEAT_THIS_CHECKPOINT"
            )
        if not is_valid_checkpoint(self._checkpoint, self._sha256):
            raise PermanentStepError(
                f"Los pesos de beat_this en {self._checkpoint} están corruptos: borralos y "
                "corré scripts/install.ps1"
            )
        try:
            from beat_this.inference import File2Beats
        except ImportError as error:
            raise PermanentStepError(
                "beat_this no está instalado: corré scripts/install.ps1 (extra 'analysis')"
            ) from error
        return File2Beats(checkpoint_path=str(self._checkpoint), device=self._device, dbn=False)

    def track(self, wav_path: Path) -> BeatGrid:
        if self._model is None:
            self._model = self._load()
        beats, downbeats = self._model(str(wav_path))
        return BeatGrid(tuple(float(t) for t in beats), tuple(float(t) for t in downbeats))
