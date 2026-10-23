"""Adaptador de BTC (jayg996/BTC-ISMIR19, MIT), vocabulario `voca`, en CPU.

BTC no es un paquete: `scripts/install.ps1` clona el repo en un commit fijo dentro de la caché
(`<GUITAR_CACHE_DIR>/btc`, o `GUITAR_BTC_DIR`). Los dos arreglos de compatibilidad con
dependencias actuales (`yaml.safe_load` en vez de `yaml.load` y el alias `np.float`) se aplican
acá en tiempo de ejecución, sin tocar los archivos del clon, así el clon queda siempre limpio.

torch, numpy, librosa y yaml se importan recién al reconocer: el resto del worker (y sus tests)
no los necesita.
"""

import sys
from pathlib import Path
from typing import Any

from guitarra_worker.domain.chords import RawChord
from guitarra_worker.pipeline.step import PermanentStepError

VOCA_WEIGHTS = ("test", "btc_model_large_voca.pt")
VOCA_CHORDS = 170
INSTALL_HINT = "corré scripts/install.ps1 (clona BTC) o poné GUITAR_BTC_DIR en el .env"


def is_installed(btc_dir: Path) -> bool:
    return (btc_dir / "btc_model.py").is_file() and (btc_dir.joinpath(*VOCA_WEIGHTS)).is_file()


class BtcChordRecognizer:
    name = "btc-voca"

    def __init__(self, btc_dir: Path) -> None:
        self._btc_dir = btc_dir
        self._loaded: tuple[Any, ...] | None = None

    def recognize(self, wav_path: Path) -> list[RawChord]:
        config, model, mean, std, labels = self._load()
        import numpy as np
        import torch
        from utils.mir_eval_modules import audio_file_to_features

        feature, per_second, _ = audio_file_to_features(str(wav_path), config)
        feature = (feature.T - mean) / std
        step = config.model["timestep"]
        padding = step - (feature.shape[0] % step)
        feature = np.pad(feature, ((0, padding), (0, 0)))
        x = torch.tensor(feature, dtype=torch.float32).unsqueeze(0)
        ids: list[int] = []
        with torch.no_grad():
            for t in range(feature.shape[0] // step):
                out, _ = model.self_attn_layers(x[:, step * t : step * (t + 1), :])
                prediction, _ = model.output_layer(out)
                ids += prediction.squeeze().tolist()
        ids = ids[: len(ids) - padding]
        return _runs(ids, per_second, labels)

    def _load(self) -> tuple[Any, ...]:
        if self._loaded is None:
            if not is_installed(self._btc_dir):
                raise PermanentStepError(f"No encuentro BTC en {self._btc_dir}: {INSTALL_HINT}")
            self._loaded = _load_voca(self._btc_dir)
        return self._loaded


def _runs(ids: list[int], per_second: float, labels: dict[int, str]) -> list[RawChord]:
    """Agrupa los ids consecutivos iguales en tramos con tiempos en segundos."""
    runs: list[RawChord] = []
    start = 0
    for i in range(1, len(ids) + 1):
        if i == len(ids) or ids[i] != ids[start]:
            runs.append(RawChord(start * per_second, i * per_second, labels[ids[start]]))
            start = i
    return runs


def _load_voca(btc_dir: Path) -> tuple[Any, ...]:
    import numpy as np
    import torch
    import yaml

    np.float = float  # type: ignore[attr-defined]  # el repo usa el alias, eliminado en numpy 1.24
    if str(btc_dir) not in sys.path:
        sys.path.insert(0, str(btc_dir))
    from btc_model import BTC_model
    from utils.hparams import HParams
    from utils.mir_eval_modules import idx2voca_chord

    config = HParams(**yaml.safe_load((btc_dir / "run_config.yaml").read_text(encoding="utf-8")))
    config.feature["large_voca"] = True
    config.model["num_chords"] = VOCA_CHORDS
    model = BTC_model(config=config.model)
    # weights_only=True: el .pt solo puede traer tensores y arrays, nunca código ejecutable.
    # Ojo: `np._core.multiarray` es API privada de numpy 2 (acotada por `numpy>=2`); revisarla al
    # subir numpy.
    torch.serialization.add_safe_globals(
        [
            (np._core.multiarray.scalar, "numpy.core.multiarray.scalar"),
            (np._core.multiarray._reconstruct, "numpy.core.multiarray._reconstruct"),
            np.ndarray,
            np.dtype,
            type(np.dtype("float32")),
            type(np.dtype("float64")),
        ]
    )
    checkpoint = torch.load(btc_dir.joinpath(*VOCA_WEIGHTS), map_location="cpu", weights_only=True)
    model.load_state_dict(checkpoint["model"])
    return config, model.eval(), checkpoint["mean"], checkpoint["std"], idx2voca_chord()
