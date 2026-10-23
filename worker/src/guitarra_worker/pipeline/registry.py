"""Lista ordenada de pasos del pipeline. T06 a T13 suman los reales acá."""

from typing import Any

from guitarra_worker.adapters.audio_features import LibrosaSelfSimilarity
from guitarra_worker.adapters.beat_this import BeatThisTracker
from guitarra_worker.adapters.spotify import SpotifyAdapter
from guitarra_worker.adapters.youtube import YoutubeAdapter
from guitarra_worker.config import Settings
from guitarra_worker.pipeline.step import PipelineContext, Step
from guitarra_worker.steps.download import DownloadStep
from guitarra_worker.steps.source import SourceStep
from guitarra_worker.steps.structure import StructureStep
from guitarra_worker.steps.tempo import TempoStep


class NoopStep:
    """Paso de ejemplo: devuelve un resultado vacío con la forma que espera la API."""

    name = "noop"
    version = "1"

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        return {"metadata": {}, "sections": [], "charts": []}


def assemble_result(outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Arma el cuerpo del result (`metadata`, `sections`, `charts`) con las salidas de los pasos.

    T13 lo reemplaza para leer la salida del paso de armado.
    """
    return outputs["noop"]


def default_steps(settings: Settings | None = None) -> list[Step]:
    """Pasos reales en orden. Spotify solo funciona si hay credenciales en la config."""
    settings = settings or Settings()
    youtube = YoutubeAdapter(settings.ffmpeg)
    spotify = SpotifyAdapter(settings.spotify_client_id, settings.spotify_client_secret)
    beat_tracker = BeatThisTracker(settings.beat_this_checkpoint_path, settings.beat_this_sha256)
    return [
        SourceStep(youtube, spotify),
        DownloadStep(youtube),
        TempoStep(beat_tracker),
        StructureStep(LibrosaSelfSimilarity()),
    ]
