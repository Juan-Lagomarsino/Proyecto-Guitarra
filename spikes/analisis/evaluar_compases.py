"""Proxy de calidad de los downbeats (no hay compases de referencia).

Los cambios de acorde de BTC caen mayormente en el primer tiempo del compás. Para cada herramienta
se mide qué parte de los cambios (a +-TOL s de un beat) cae sobre los downbeats declarados, y se compara con la
mejor de las 4 fases posibles de la grilla: si la herramienta acertó la fase, ambos números coinciden.
"""

import json
from pathlib import Path

import numpy as np
from acordes_comun import leer_linea
from songs import SONGS

BEATS = Path(__file__).parent / "resultados" / "beats"
TOL = 0.12


def cambios(slug: str) -> np.ndarray:
    tramos = [
        t
        for t in leer_linea("btc_voca", slug)["tramos"]
        if t[1] - t[0] >= 0.4 and t[2] not in ("N", "X")
    ]
    return np.array([t[0] for t in tramos[1:]])


def evaluar(herramienta: str, slug: str) -> dict:
    datos = json.loads((BEATS / herramienta / f"{slug}.json").read_text())
    beats, downbeats = np.array(datos["beats"]), np.array(datos["downbeats"])
    cam = cambios(slug)
    indice = np.abs(beats[None, :] - cam[:, None]).argmin(axis=1)
    cerca = np.abs(beats[indice] - cam) <= TOL
    indice = indice[cerca]
    es_down = np.isin(beats[indice], downbeats)
    fases = [np.mean((indice % 4) == p) for p in range(4)]
    return {
        "cambios_en_beat": round(float(cerca.mean()), 3),
        "en_downbeats_declarados": round(float(es_down.mean()), 3),
        "mejor_fase": round(float(max(fases)), 3),
    }


if __name__ == "__main__":
    salida = {}
    for h in ("beat_this", "librosa"):
        salida[h] = {s: evaluar(h, s) for s in SONGS}
        for s, r in salida[h].items():
            print(h, s, r)
    (Path(__file__).parent / "resultados" / "compases.json").write_text(
        json.dumps(salida, indent=2)
    )
