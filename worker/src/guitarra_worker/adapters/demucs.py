"""Separación de pistas con Demucs `htdemucs_6s` (ADR 0015). Solo CPU, imports perezosos.

`Separator` es la interfaz que ven los pasos; `DemucsSeparator` la implementa. Si `demucs` o
`torch` no están, o faltan los pesos, falla con `PermanentStepError` explicando cómo instalarlo
(los demás trabajos del worker no se ven afectados).

Uso como script (lo llama scripts/install.ps1 para bajar los pesos, con reintentos):
`python -m guitarra_worker.adapters.demucs`.
"""

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from math import gcd
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

from guitarra_worker.config import Settings
from guitarra_worker.domain.mixing import STEM_NAMES
from guitarra_worker.pipeline.step import PermanentStepError

MODEL_NAME = "htdemucs_6s"
DOWNLOAD_ATTEMPTS = 3
RETRY_WAIT_S = 10.0
INSTALL_HINT = "corré scripts/install.ps1 (instala demucs y baja los pesos de htdemucs_6s)"
WEIGHTS_PATTERN = "checkpoints/*.th"  # torch.hub guarda ahí los pesos que baja demucs


class Separator(Protocol):
    def separate(
        self, wav_path: Path, out_dir: Path, progress: Callable[[str], None] | None = ...
    ) -> dict[str, Path]:
        """Escribe una pista WAV (float32 estéreo) por instrumento y devuelve nombre -> archivo.

        Los nombres son los de `STEM_NAMES`: drums, bass, other, vocals, guitar, piano.
        """
        ...


def has_weights(model_dir: Path) -> bool:
    return any(model_dir.glob(WEIGHTS_PATTERN))


def read_wav_float(path: Path) -> tuple[int, np.ndarray]:
    rate, data = wavfile.read(path)
    if data.dtype.kind == "i":
        data = data.astype(np.float32) / np.iinfo(data.dtype).max
    elif data.dtype.kind != "f":
        raise PermanentStepError(
            f"Formato de WAV no soportado ({data.dtype}) en {path.name}: "
            "hace falta PCM de 16/32 bits con signo o float"
        )
    data = data.astype(np.float32)
    return rate, data[:, None] if data.ndim == 1 else data


def write_wav_float(path: Path, rate: int, data: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(path, rate, np.ascontiguousarray(data, dtype=np.float32))


def _resample(data: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate:
        return data
    divisor = gcd(source_rate, target_rate)
    return resample_poly(data, target_rate // divisor, source_rate // divisor, axis=0)


@dataclass(frozen=True)
class Normalization:
    mean: float
    std: float


def normalize_mix(mix: np.ndarray) -> tuple[np.ndarray, Normalization]:
    """Como `demucs.separate`: `ref = mix.mean(canales); (mix - ref.mean()) / ref.std()`.

    `mix` es `(canales, muestras)`. Con silencio total (std 0) no se divide.
    """
    ref = mix.mean(axis=0)
    mean, std = float(ref.mean()), float(ref.std())
    std = std if std > 0 else 1.0
    return (mix - mean) / std, Normalization(mean, std)


def denormalize_sources(sources: np.ndarray, norm: Normalization) -> np.ndarray:
    """Inversa de `normalize_mix` sobre las pistas `(pistas, canales, muestras)`."""
    return sources * norm.std + norm.mean


class ModelRunner(Protocol):
    """Lo mínimo del modelo que usa el separador (aísla torch para poder testear sin él)."""

    samplerate: int
    sources: list[str]

    def run(self, mix: np.ndarray) -> np.ndarray:
        """`(2, muestras)` normalizada -> `(pistas, 2, muestras)`."""
        ...


class TorchRunner:
    def __init__(self, torch: Any, apply_model: Any, model: Any) -> None:
        self._torch, self._apply_model, self._model = torch, apply_model, model
        self.samplerate: int = model.samplerate
        self.sources: list[str] = list(model.sources)

    def run(self, mix: np.ndarray) -> np.ndarray:
        tensor = self._torch.from_numpy(np.ascontiguousarray(mix[None], dtype=np.float32))
        with self._torch.no_grad():
            out = self._apply_model(self._model, tensor, device="cpu", split=True, progress=False)
        return out[0].numpy()


class DemucsSeparator:
    def __init__(self, model_dir: Path, runner: ModelRunner | None = None) -> None:
        self._model_dir = model_dir
        self._runner = runner

    def _load_libs(self) -> tuple[Any, Any, Any]:
        try:
            import torch
            from demucs.apply import apply_model
            from demucs.pretrained import get_model
        except ImportError as exc:
            raise PermanentStepError(
                f"Falta demucs o torch en el venv del worker ({exc}): {INSTALL_HINT}"
            ) from exc
        return torch, apply_model, get_model

    def _load_runner(self) -> ModelRunner:
        if self._runner is not None:
            return self._runner
        torch, apply_model, get_model = self._load_libs()
        if not has_weights(self._model_dir):
            raise PermanentStepError(
                f"No están los pesos de {MODEL_NAME} en {self._model_dir}: {INSTALL_HINT}"
            )
        torch.hub.set_dir(str(self._model_dir))
        model = get_model(MODEL_NAME)
        model.cpu().eval()
        return TorchRunner(torch, apply_model, model)

    def separate(
        self, wav_path: Path, out_dir: Path, progress: Callable[[str], None] | None = None
    ) -> dict[str, Path]:
        runner = self._load_runner()
        if list(runner.sources) != list(STEM_NAMES):
            raise PermanentStepError(f"El modelo trae pistas inesperadas: {runner.sources}")
        rate, audio = read_wav_float(wav_path)
        audio = _resample(audio, rate, runner.samplerate)
        if audio.shape[1] == 1:
            audio = np.repeat(audio, 2, axis=1)
        mix, norm = normalize_mix(audio.T[:2])
        if progress:
            progress("Separando pistas con Demucs (CPU, tarda varios minutos)")
        sources = denormalize_sources(runner.run(mix), norm)
        stems: dict[str, Path] = {}
        for name, stem in zip(runner.sources, sources, strict=True):
            stems[name] = out_dir / f"{name}.wav"
            write_wav_float(stems[name], runner.samplerate, stem.T)
        return stems


def ensure_weights(
    settings: Settings,
    sleep: Callable[[float], None] = time.sleep,
    load: Callable[[str], Any] | None = None,
) -> Path:
    """Baja `htdemucs_6s` a la carpeta de modelos (idempotente, con reintentos)."""
    model_dir = settings.demucs_model_path
    if has_weights(model_dir):
        return model_dir
    import torch
    from demucs.pretrained import get_model

    model_dir.mkdir(parents=True, exist_ok=True)
    torch.hub.set_dir(str(model_dir))
    loader = load or get_model
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            loader(MODEL_NAME)
            return model_dir
        except Exception as error:  # noqa: BLE001 - red, disco o repo caído: se reintenta
            print(f"Falló la bajada ({attempt}/{DOWNLOAD_ATTEMPTS}): {error}", file=sys.stderr)
            if attempt < DOWNLOAD_ATTEMPTS:
                sleep(RETRY_WAIT_S)
    raise RuntimeError(f"No pude bajar los pesos de {MODEL_NAME} a {model_dir}")


def main() -> int:
    try:
        path = ensure_weights(Settings())
    except (RuntimeError, ImportError) as error:
        print(error, file=sys.stderr)
        return 1
    print(f"Pesos de {MODEL_NAME} listos: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
