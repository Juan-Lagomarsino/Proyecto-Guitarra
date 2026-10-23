"""BTC (Bi-directional Transformer for Chord recognition, jayg996/BTC-ISMIR19) en CPU.

Reimplementa test.py del repo original con dos arreglos para dependencias actuales
(yaml.safe_load y carga de pesos). El repo se clona a la caché del spike:
    git clone --depth 1 https://github.com/jayg996/BTC-ISMIR19.git <CACHE>/btc
Uso: python acordes_btc.py [voca|majmin]
"""

import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
import yaml
from acordes_comun import guardar_linea
from songs import CACHE, SONGS, wav_path

BTC_DIR = Path(os.environ.get("BTC_DIR", CACHE / "btc"))
sys.path.insert(0, str(BTC_DIR))
np.float = float  # el repo usa el alias np.float, eliminado en numpy >= 1.24

from btc_model import BTC_model
from utils.hparams import HParams
from utils.mir_eval_modules import audio_file_to_features, idx2chord, idx2voca_chord


def cargar(voca: bool):
    config = HParams(**yaml.safe_load((BTC_DIR / "run_config.yaml").read_text()))
    if voca:
        config.feature["large_voca"] = True
        config.model["num_chords"] = 170
        pesos, etiquetas = (
            BTC_DIR / "test" / "btc_model_large_voca.pt",
            idx2voca_chord(),
        )
    else:
        pesos, etiquetas = BTC_DIR / "test" / "btc_model.pt", idx2chord
    modelo = BTC_model(config=config.model)
    # weights_only=True: el .pt solo puede traer tensores y arrays, nunca código ejecutable.
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
    ckpt = torch.load(pesos, map_location="cpu", weights_only=True)
    modelo.load_state_dict(ckpt["model"])
    return config, modelo.eval(), ckpt["mean"], ckpt["std"], etiquetas


def reconocer(
    ruta: Path, config, modelo, media, desv, etiquetas
) -> list[tuple[float, float, str]]:
    feature, por_segundo, _ = audio_file_to_features(str(ruta), config)
    feature = (feature.T - media) / desv
    paso = config.model["timestep"]
    relleno = paso - (feature.shape[0] % paso)
    feature = np.pad(feature, ((0, relleno), (0, 0)))
    x = torch.tensor(feature, dtype=torch.float32).unsqueeze(0)
    ids: list[int] = []
    with torch.no_grad():
        for t in range(feature.shape[0] // paso):
            salida, _ = modelo.self_attn_layers(x[:, paso * t : paso * (t + 1), :])
            pred, _ = modelo.output_layer(salida)
            ids += pred.squeeze().tolist()
    ids = ids[: len(ids) - relleno]
    tramos, inicio = [], 0
    for i in range(1, len(ids) + 1):
        if i == len(ids) or ids[i] != ids[inicio]:
            tramos.append(
                (inicio * por_segundo, i * por_segundo, etiquetas[ids[inicio]])
            )
            inicio = i
    return tramos


if __name__ == "__main__":
    variante = sys.argv[1] if len(sys.argv) > 1 else "voca"
    config, modelo, media, desv, etiquetas = cargar(variante == "voca")
    for slug in SONGS:
        t0 = time.perf_counter()
        tramos = reconocer(wav_path(slug), config, modelo, media, desv, etiquetas)
        seg = time.perf_counter() - t0
        guardar_linea(f"btc_{variante}", slug, tramos, seg)
        print(f"btc_{variante}", slug, len(tramos), "tramos", f"{seg:.1f}s", flush=True)
