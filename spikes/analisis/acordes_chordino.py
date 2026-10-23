"""Chordino (plugin Vamp nnls-chroma) vía Sonic Annotator, sin instalar nada en el sistema.

Los DLL salen de `extraer_vamp.py`. No se usa el paquete `vamp` de pip: no tiene rueda para Windows
y exige compilar. Uso: python acordes_chordino.py <dir de plugins> <sonic-annotator.exe>
"""

import csv
import io
import os
import subprocess
import sys
import time
from pathlib import Path

from acordes_comun import guardar_linea
from songs import SONGS, wav_path


def correr(sonic: Path, plugins: Path, wav: Path) -> list:
    nombre = next(p.stem for p in plugins.glob("nnls-chroma-*.dll"))
    entorno = {**os.environ, "VAMP_PATH": str(plugins)}
    comando = [
        str(sonic),
        "-d",
        f"vamp:{nombre}:chordino:simplechord",
        "-w",
        "csv",
        "--csv-stdout",
        str(wav),
    ]
    salida = subprocess.run(
        comando, capture_output=True, text=True, env=entorno, check=True
    ).stdout
    filas = [f for f in csv.reader(io.StringIO(salida)) if len(f) == 3 and not f[0]]
    puntos = [(float(f[1]), f[2]) for f in filas]
    return [
        (t, puntos[i + 1][0] if i + 1 < len(puntos) else t + 1, c)
        for i, (t, c) in enumerate(puntos)
    ]


if __name__ == "__main__":
    plugins, sonic = Path(sys.argv[1]), Path(sys.argv[2])
    for slug in SONGS:
        t0 = time.perf_counter()
        tramos = correr(sonic, plugins, wav_path(slug))
        segundos = time.perf_counter() - t0
        guardar_linea("chordino", slug, tramos, segundos)
        print(slug, len(tramos), f"{segundos:.1f}s")
