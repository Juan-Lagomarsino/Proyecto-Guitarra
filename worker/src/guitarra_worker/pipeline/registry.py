"""Lista ordenada de pasos del pipeline y cómo sale de ahí el resultado para la API."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from guitarra_worker.adapters.audio_features import LibrosaSelfSimilarity
from guitarra_worker.adapters.beat_this import BeatThisTracker
from guitarra_worker.adapters.btc import BtcChordRecognizer
from guitarra_worker.adapters.demucs import DemucsSeparator, Separator
from guitarra_worker.adapters.ffmpeg import convert_to_m4a, find_ffmpeg
from guitarra_worker.adapters.spotify import SpotifyAdapter
from guitarra_worker.adapters.transcriber import BasicPitchTranscriber, Transcriber
from guitarra_worker.adapters.youtube import YoutubeAdapter
from guitarra_worker.config import Settings
from guitarra_worker.pipeline.step import Step
from guitarra_worker.steps.assemble import AssembleStep
from guitarra_worker.steps.chords import ChordsStep
from guitarra_worker.steps.cifraclub import CifraClubStep
from guitarra_worker.steps.download import DownloadStep
from guitarra_worker.steps.key import KeyStep
from guitarra_worker.steps.publish_audio import AssetUploader, PublishAudioStep
from guitarra_worker.steps.riffs import BuildRiffsStep, RiffsStep, chart_info_of
from guitarra_worker.steps.separate import (
    MixNoGuitarStep,
    SeparateStep,
    SeparationDownloadStep,
    SeparationSourceStep,
)
from guitarra_worker.steps.source import SourceStep
from guitarra_worker.steps.structure import StructureStep
from guitarra_worker.steps.strum import StrumStep
from guitarra_worker.steps.tempo import TempoStep
from guitarra_worker.strum.ollama_chooser import OllamaChooser

RESULT_STEP = AssembleStep.name


def assemble_result(outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Cuerpo del result (`metadata`, `sections`, `charts`): la salida del paso de armado."""
    return outputs[RESULT_STEP]


def _to_m4a(ffmpeg: str | None) -> Callable[[Path, Path], None]:
    def convert(source: Path, dest: Path) -> None:
        convert_to_m4a(find_ffmpeg(ffmpeg), source, dest)

    return convert


def default_steps(
    settings: Settings | None = None, uploader: AssetUploader | None = None
) -> list[Step]:
    """Pasos reales en orden. Spotify solo funciona si hay credenciales en la config.

    Con `uploader` (el cliente de la API) se agrega `publish_audio` después de la descarga.
    """
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
    if uploader is not None:
        steps.insert(2, PublishAudioStep(_to_m4a(settings.ffmpeg), uploader))
    return [*steps, AssembleStep({step.name: step.version for step in steps})]


def separation_steps(
    uploader: AssetUploader,
    settings: Settings | None = None,
    separator: Separator | None = None,
    transcriber: Transcriber | None = None,
) -> list[Step]:
    """Pipeline del trabajo `separation`: descarga (si no está en caché) -> separar -> mezclar sin
    guitarra -> m4a -> subir como `no_guitar` -> riffs (transcribir la pista de guitarra y digitar).
    Sin Demucs instalado falla recién en `separate`; sin basic-pitch o sin chart no hay riffs."""
    settings = settings or Settings()
    separator = separator or DemucsSeparator(settings.demucs_model_path)
    publish = PublishAudioStep(
        _to_m4a(settings.ffmpeg),
        uploader,
        kind="no_guitar",
        source=("mix_no_guitar", "mix_path"),
        name="publish_no_guitar",
    )
    return [
        SeparationSourceStep(),
        SeparationDownloadStep(YoutubeAdapter(settings.ffmpeg)),
        SeparateStep(separator),
        MixNoGuitarStep(),
        publish,
        RiffsStep(transcriber or BasicPitchTranscriber(), chart_info_of),
        BuildRiffsStep(),
    ]
