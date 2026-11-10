"""Mide los transcriptores sobre audio real contra una referencia simple (para correr en la PC).

    python medir_audio_real.py pista_guitar.wav referencia.json
    python medir_audio_real.py pista_guitar.wav referencia.tsv --barrido
    python medir_audio_real.py pista_guitar.wav referencia.tsv --desde 12.5 --hasta 20 --lista

El WAV es p. ej. la pista `guitar` que deja Demucs. La referencia es la tab del riff pasada a
tiempos (formatos en el README). `--desde/--hasta` recortan WAV y referencia al mismo tramo
(los tiempos de la referencia se leen en segundos del archivo completo). `--lista` imprime las
notas estimadas junto a las de referencia para ver qué falla. Imprime precisión, recall y F1 (onset
+-50 ms, altura exacta; con y sin offsets) y el tiempo, igual que `medir.py`.
"""

import argparse
import tempfile
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from medir import GRILLA
from metricas import evaluar, leer_referencia
from transcribir import basic_pitch_notas, pyin_notas


def recortar(wav: Path, desde: float, hasta: float | None, destino: Path) -> Path:
    audio, sr = sf.read(wav)
    fin = None if hasta is None else int(hasta * sr)
    sf.write(destino, audio[int(desde * sr) : fin], sr)
    return destino


def recortar_referencia(ref: np.ndarray, desde: float, hasta: float | None) -> np.ndarray:
    corte = ref[ref[:, 0] >= desde].copy()
    if hasta is not None:
        corte = corte[corte[:, 0] < hasta]
    corte[:, :2] -= desde
    return corte


def informar(nombre: str, ref: np.ndarray, est: np.ndarray, segundos: float) -> None:
    m = evaluar(ref, est)
    print(
        f"{nombre:28s} notas ref={len(ref):3d} est={len(est):3d} "
        f"P={m['p']:.2f} R={m['r']:.2f} F1={m['f1']:.2f} | "
        f"con offsets P={m['p_off']:.2f} R={m['r_off']:.2f} F1={m['f1_off']:.2f} | {segundos:.1f} s"
    )


def listar(ref: np.ndarray, est: np.ndarray) -> None:
    print("  referencia (onset, offset, midi):")
    for fila in ref:
        print(f"    {fila[0]:7.3f} {fila[1]:7.3f} {int(fila[2])}")
    print("  estimadas:")
    for fila in est:
        print(f"    {fila[0]:7.3f} {fila[1]:7.3f} {int(fila[2])}")


def correr(wav: Path, ref: np.ndarray, args: argparse.Namespace) -> None:
    basic_pitch_notas(wav)  # carga el modelo fuera del cronómetro
    candidatos = {"basic_pitch": basic_pitch_notas, "pyin": pyin_notas}
    for nombre, fn in candidatos.items():
        t0 = time.perf_counter()
        est = fn(wav)
        informar(nombre, ref, est, time.perf_counter() - t0)
        if args.lista:
            listar(ref, est)
    if args.barrido:
        import itertools

        for ot, ft, mn in itertools.product(*GRILLA.values()):
            est = basic_pitch_notas(
                wav, onset_threshold=ot, frame_threshold=ft, minimum_note_length=mn
            )
            informar(f"bp onset={ot} frame={ft} min={mn}", ref, est, 0.0)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("wav", type=Path)
    p.add_argument("referencia", type=Path)
    p.add_argument("--desde", type=float, default=0.0)
    p.add_argument("--hasta", type=float, default=None)
    p.add_argument("--barrido", action="store_true", help="probar la grilla de umbrales")
    p.add_argument("--lista", action="store_true", help="imprimir las notas")
    args = p.parse_args()

    ref = leer_referencia(args.referencia)
    recorte = args.desde > 0 or args.hasta is not None
    if not recorte:
        correr(args.wav, ref, args)
        return
    ref = recortar_referencia(ref, args.desde, args.hasta)
    with tempfile.TemporaryDirectory() as tmp:
        wav = recortar(args.wav, args.desde, args.hasta, Path(tmp) / "recorte.wav")
        correr(wav, ref, args)


if __name__ == "__main__":
    main()
