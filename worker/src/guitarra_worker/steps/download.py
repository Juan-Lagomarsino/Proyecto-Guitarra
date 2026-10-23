"""Paso 2: descargar el audio a `song_dir/original.wav` (48 kHz estéreo).

Salida: `{wav_path, sample_rate, channels, duration_s}`. `wav_path` es absoluto y `duration_s` es
la duración medida del archivo.
"""

import wave
from pathlib import Path
from typing import Any, Protocol

from guitarra_worker.adapters.ffmpeg import WavInfo, read_wav_info
from guitarra_worker.pipeline.step import (
    PermanentStepError,
    PipelineContext,
    ProgressCallback,
    RetryableStepError,
)

WAV_NAME = "original.wav"
DURATION_TOLERANCE_S = 5.0
DURATION_TOLERANCE_RATIO = 0.03


class YoutubeDownloader(Protocol):
    def download_wav(
        self, video_id: str, dest: Path, progress: ProgressCallback | None = ...
    ) -> None: ...


def _is_similar_duration(actual_s: float, expected_s: float | None) -> bool:
    if expected_s is None:
        return True
    tolerance = max(DURATION_TOLERANCE_S, expected_s * DURATION_TOLERANCE_RATIO)
    return abs(actual_s - expected_s) <= tolerance


def _read_valid(wav_path: Path, expected_s: float | None) -> WavInfo | None:
    """Info del WAV si existe, se puede leer y dura lo esperado; si no, None."""
    if not wav_path.exists():
        return None
    try:
        info = read_wav_info(wav_path)
    except (wave.Error, EOFError, OSError, ZeroDivisionError):
        return None
    return info if _is_similar_duration(info.duration_s, expected_s) else None


class DownloadStep:
    name = "download"
    version = "1"

    def __init__(self, youtube: YoutubeDownloader) -> None:
        self._youtube = youtube

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        source = ctx.outputs["source"]
        expected_s = source.get("duration_s")
        wav_path = ctx.song_dir / WAV_NAME
        info = _read_valid(wav_path, expected_s)
        if info is None:
            wav_path.unlink(missing_ok=True)
            ctx.progress("Descargando audio")
            self._youtube.download_wav(source["youtube_id"], wav_path, ctx.progress)
            info = _read_valid(wav_path, expected_s)
        if info is None:
            wav_path.unlink(missing_ok=True)
            message = f"El audio descargado no dura lo esperado (~{expected_s} s)"
            if ctx.job.attempt >= 2:  # el mismo resultado dos veces: no gastar más intentos
                raise PermanentStepError(message)
            raise RetryableStepError(f"{message}; reintento")
        ctx.progress("Audio listo")
        return {
            "wav_path": str(wav_path.resolve()),
            "sample_rate": info.sample_rate,
            "channels": info.channels,
            "duration_s": round(info.duration_s, 3),
        }
