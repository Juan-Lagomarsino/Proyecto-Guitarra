"""ffmpeg: ubicar el ejecutable, convertir a WAV y leer el encabezado de un WAV."""

import os
import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

from guitarra_worker.pipeline.step import PermanentStepError, RetryableStepError

SAMPLE_RATE = 48_000
# Mensajes de ffmpeg que reintentar no arregla: formato o códec que no soporta.
UNSUPPORTED_MARKERS = ("unsupported", "unknown decoder", "unknown encoder", "could not find codec")
CHANNELS = 2  # estéreo: Demucs trabaja en estéreo; el mono se deriva en los pasos que lo necesiten


@dataclass(frozen=True)
class WavInfo:
    sample_rate: int
    channels: int
    duration_s: float


def find_ffmpeg(configured: str | None = None) -> str:
    """Ruta de ffmpeg: la de `GUITAR_FFMPEG` si está, si no la del PATH."""
    found = configured if configured else shutil.which("ffmpeg")
    if not found:
        raise PermanentStepError(
            "No encuentro ffmpeg: instalalo (scripts/install.ps1) o poné GUITAR_FFMPEG en el .env"
        )
    return found


def _command(ffmpeg: str, source: Path, partial: Path) -> list[str]:
    return [
        *(ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source)),
        *("-vn", "-ac", str(CHANNELS), "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le"),
        *("-f", "wav", str(partial)),
    ]


def convert_to_wav(ffmpeg: str, source: Path, dest: Path) -> None:
    """Convierte a WAV 48 kHz estéreo de 16 bits. Escritura atómica: temporal + rename."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    if source.stat().st_size == 0:
        raise RetryableStepError("El audio descargado está vacío; reintento")
    try:
        result = subprocess.run(
            _command(ffmpeg, source, partial), capture_output=True, text=True, check=False
        )
    except OSError as exc:
        raise PermanentStepError(f"No pude ejecutar ffmpeg ({ffmpeg}): {exc}") from exc
    if result.returncode != 0:
        partial.unlink(missing_ok=True)
        detail = result.stderr.strip()[-500:]
        message = f"ffmpeg no pudo convertir el audio: {detail}"
        if any(marker in detail.lower() for marker in UNSUPPORTED_MARKERS):
            raise PermanentStepError(message)
        # Entrada truncada o error de I/O: una nueva descarga puede salir bien.
        raise RetryableStepError(message)
    os.replace(partial, dest)


def read_wav_info(path: Path) -> WavInfo:
    with wave.open(str(path), "rb") as wav:
        rate = wav.getframerate()
        return WavInfo(rate, wav.getnchannels(), wav.getnframes() / rate)
