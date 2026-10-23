"""Lista ordenada de pasos del pipeline y cómo sale de ahí el resultado para la API."""

from typing import Any

from guitarra_worker.adapters.audio_features import LibrosaSelfSimilarity
from guitarra_worker.adapters.beat_this import BeatThisTracker
from guitarra_worker.adapters.btc import BtcChordRecognizer
from guitarra_worker.adapters.spotify import SpotifyAdapter
from guitarra_worker.adapters.youtube import YoutubeAdapter
from guitarra_worker.config import Settings
from guitarra_worker.pipeline.step import Step
from guitarra_worker.steps.assemble import AssembleStep
from guitarra_worker.steps.chords import ChordsStep
from guitarra_worker.steps.cifraclub import CifraClubStep
from guitarra_worker.steps.download import DownloadStep
from guitarra_worker.steps.key import KeyStep
from guitarra_worker.steps.source import SourceStep
from guitarra_worker.steps.structure import StructureStep
from guitarra_worker.steps.strum import StrumStep
from guitarra_worker.steps.tempo import TempoStep
from guitarra_worker.strum.ollama_chooser import OllamaChooser

RESULT_STEP = AssembleStep.name


def assemble_result(outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Cuerpo del result (`metadata`, `sections`, `charts`): la salida del paso de armado."""
    return outputs[RESULT_STEP]


def default_steps(settings: Settings | None = None) -> list[Step]:
    """Pasos reales en orden. Spotify solo funciona si hay credenciales en la config."""
    settings = settings or Settings()
    youtube = YoutubeAdapter(settings.ffmpeg)
    spotify = SpotifyAdapter(settings.spotify_client_id, settings.spotify_client_secret)
    beat_tracker = BeatThisTracker(settings.beat_this_checkpoint_path, settings.beat_this_sha256)
    chooser = (
        OllamaChooser(settings.ollama_url, settings.ollama_model, settings.ollama_timeout_s)
        if settings.ollama_url
        else None
    )
    steps: list[Step] = [
        SourceStep(youtube, spotify),
        DownloadStep(youtube),
        TempoStep(beat_tracker),
        StructureStep(LibrosaSelfSimilarity()),
        ChordsStep(BtcChordRecognizer(settings.btc_path)),
        KeyStep(),
        CifraClubStep(),
        StrumStep(chooser),
    ]
    return [*steps, AssembleStep({step.name: step.version for step in steps})]
