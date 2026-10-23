"""Convierte el espejo safetensors de beat_this (final0) al formato .ckpt que espera la librería.

El host oficial (cloud.cp.jku.at) devolvió 503 durante el spike; ver ADR 0006.
Al espejo le faltan los buffers `rotary_embed.freqs`, que son deterministas (se
calculan al construir el modelo), así que se completan desde un modelo recién creado.
"""

import sys
from pathlib import Path

import torch
from beat_this.model.beat_tracker import BeatThis
from safetensors.torch import load_file

origen, destino = Path(sys.argv[1]), Path(sys.argv[2])
cargado = load_file(str(origen))
completo = BeatThis().state_dict()
inesperadas = set(cargado) - set(completo)
assert not inesperadas, inesperadas
completo.update(cargado)
faltantes = set(completo) - set(cargado)
print("completadas desde el modelo nuevo:", sorted(faltantes))
torch.save(
    {
        "hyper_parameters": {},
        "state_dict": {f"model.{k}": v for k, v in completo.items()},
    },
    destino,
)
