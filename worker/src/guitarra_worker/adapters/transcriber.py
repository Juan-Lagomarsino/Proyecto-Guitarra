"""Transcripción de la pista de guitarra a notas con basic-pitch (ADR 0017). Import perezoso.

`Transcriber` es la interfaz que ve el paso; `BasicPitchTranscriber` la implementa con el modelo
ONNX que trae el paquete (sin TensorFlow). Si basic-pitch no está instalado levanta
`TranscriberUnavailable`: el paso de riffs se saltea con un aviso y el trabajo no falla.
Los offsets de basic-pitch son malos y los bends no se detectan; la cuantización lo tiene en cuenta.
"""

from pathlib import Path
from typing import Any, Protocol

from guitarra_worker.domain.quantize import TimedNote

INSTALL_HINT = (
    "corré scripts/install.ps1 (instala el extra `riffs`: basic-pitch 0.4.0 y onnxruntime)"
)
# Umbrales elegidos con el barrido del spike (docs/adr/0017-transcripcion-de-riffs.md)
ONSET_THRESHOLD = 0.7
FRAME_THRESHOLD = 0.4
MINIMUM_NOTE_LENGTH_MS = 58.0


class TranscriberUnavailable(Exception):
    """No se puede transcribir en esta máquina (falta la librería): no es un error del trabajo."""


class Transcriber(Protocol):
    def transcribe(self, wav_path: Path) -> list[TimedNote]:
        """Notas `{onset_s, offset_s, midi, confidence}` ordenadas por ataque."""
        ...


class BasicPitchTranscriber:
    def __init__(self) -> None:
        self._model: Any = None

    def _load_model(self) -> Any:
        if self._model is None:
            try:
                from basic_pitch.inference import ICASSP_2022_MODEL_PATH, Model
            except ImportError as exc:
                raise TranscriberUnavailable(
                    f"Falta basic-pitch en el venv del worker ({exc}): {INSTALL_HINT}"
                ) from exc
            self._model = Model(ICASSP_2022_MODEL_PATH)
        return self._model

    def transcribe(self, wav_path: Path) -> list[TimedNote]:
        model = self._load_model()
        from basic_pitch.inference import predict

        _, _, events = predict(
            wav_path,
            model,
            onset_threshold=ONSET_THRESHOLD,
            frame_threshold=FRAME_THRESHOLD,
            minimum_note_length=MINIMUM_NOTE_LENGTH_MS,
        )
        # evento = (inicio, fin, midi, amplitud, bends); la amplitud hace de confianza
        notes = [
            TimedNote(float(e[0]), float(e[1]), int(e[2]), min(max(float(e[3]), 0.0), 1.0))
            for e in events
        ]
        return sorted(notes, key=lambda n: (n.onset_s, n.midi))
