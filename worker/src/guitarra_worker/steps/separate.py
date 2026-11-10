"""Pasos del trabajo de separación (ADR 0015): fuente -> descarga -> pistas -> mezcla sin guitarra.

La conversión a m4a y la subida son `PublishAudioStep(kind="no_guitar")`. Los pasos llevan nombres
propios (`separation_*`) para no pisar la caché de pasos del análisis de la misma canción; el WAV
descargado sí se comparte (misma carpeta por youtube_id).

Cada paso es cacheable por el runner: una segunda corrida no vuelve a separar ni a mezclar.
"""

from pathlib import Path
from typing import Any

from guitarra_worker.adapters.demucs import Separator, read_wav_float, write_wav_float
from guitarra_worker.domain.mixing import STEM_NAMES, mix_without_guitar
from guitarra_worker.pipeline.step import PermanentStepError, PipelineContext
from guitarra_worker.steps.download import DownloadStep

STEMS_DIR = "stems"
MIX_NAME = "no_guitar.wav"


class SeparationSourceStep:
    """El claim de una separación ya trae el `youtube_id`: no hay nada que resolver."""

    name = "separation_source"
    version = "1"

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        if not ctx.job.youtube_id:
            raise PermanentStepError("El trabajo de separación no trae youtube_id")
        return {"youtube_id": ctx.job.youtube_id, "duration_s": None}


class SeparationDownloadStep(DownloadStep):
    """Misma descarga que el análisis (reusa el WAV si ya está), con caché de paso propia."""

    name = "separation_download"

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        ctx.outputs["source"] = ctx.outputs["separation_source"]
        return super().run(ctx)


class SeparateStep:
    name = "separate"
    version = "1"

    def __init__(self, separator: Separator) -> None:
        self._separator = separator

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        wav_path = Path(ctx.outputs["separation_download"]["wav_path"])
        stems = self._separator.separate(wav_path, ctx.song_dir / STEMS_DIR, ctx.progress)
        missing = [name for name in STEM_NAMES if name not in stems]
        if missing:
            raise PermanentStepError(f"El separador no devolvió las pistas: {', '.join(missing)}")
        return {"stems": {name: str(path.resolve()) for name, path in stems.items()}}


class MixNoGuitarStep:
    name = "mix_no_guitar"
    version = "1"

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        paths = {name: Path(p) for name, p in ctx.outputs["separate"]["stems"].items()}
        lost = [name for name, path in paths.items() if not path.exists()]
        if lost:
            raise PermanentStepError(
                f"Faltan los archivos de las pistas ({', '.join(lost)}): "
                f"borrá {ctx.song_dir / 'steps'} para volver a separar"
            )
        ctx.progress("Mezclando sin guitarra")
        rates, stems = {}, {}
        for name, path in paths.items():
            rates[name], stems[name] = read_wav_float(path)
        if len(set(rates.values())) != 1:
            raise PermanentStepError(f"Las pistas tienen distinta frecuencia: {rates}")
        mix_path = ctx.song_dir / MIX_NAME
        write_wav_float(mix_path, next(iter(rates.values())), mix_without_guitar(stems))
        return {"mix_path": str(mix_path.resolve())}
