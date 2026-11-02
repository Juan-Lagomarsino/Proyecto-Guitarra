"""Generador de riffs sintéticos con verdad conocida (cuerda pulsada, 48 kHz).

Síntesis aditiva: armónicos con decaimiento propio (los agudos mueren antes), una pizca de
inarmonicidad y un golpe de ruido en el ataque. Permite glissando de afinación (bends) y
ataque suave (ligados). No suena a guitarra real: sirve para medir, no para escuchar.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 48_000
SALIDA = Path(__file__).parent / "salida"
SEMILLA = 7


@dataclass
class Nota:
    inicio_beat: float
    dur_beats: float
    midis: list[int]  # varias alturas = double stop / power chord (punteo simultáneo)
    ligada: bool = False  # ataque suave, sin golpe de púa (hammer-on / pull-off)
    bend_semitonos: float = 0.0  # sube este tanto durante la parte media de la nota
    vel: float = 1.0


@dataclass
class Caso:
    nombre: str
    bpm: float
    notas: list[Nota]
    ruido_db: float | None = None  # relación señal/ruido
    reverb: bool = False
    bajo_db: float | None = None  # nivel del bajo de fondo respecto del riff


def hz(midi: float) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12)


def cuerda(
    midi: int,
    dur: float,
    ligada: bool,
    bend: float,
    vel: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Una nota: `dur` de sostenido más 0,25 s de cola."""
    n = int((dur + 0.25) * SR)
    t = np.arange(n) / SR
    f0 = hz(midi)
    if bend:
        sube = np.clip((t - dur * 0.35) / (dur * 0.35), 0, 1)
        f_inst = f0 * 2.0 ** (bend * sube / 12)
    else:
        f_inst = np.full(n, f0)
    fase = 2 * np.pi * np.cumsum(f_inst) / SR
    senal = np.zeros(n)
    for k in range(1, 13):
        if f0 * k > 8000:
            break
        inarm = np.sqrt(1 + 0.0004 * k * k)
        decaimiento = np.exp(-t * (2.5 + 1.8 * k))
        senal += (1.0 / k**1.1) * decaimiento * np.sin(fase * k * inarm + rng.uniform(0, 6.28))
    ataque = 0.03 if ligada else 0.004
    senal *= np.minimum(t / ataque, 1.0) * np.clip((dur + 0.25 - t) / 0.25, 0, 1)
    if not ligada:  # golpe de púa: ráfaga corta de ruido filtrado
        rafaga = rng.normal(size=n) * np.exp(-t * 90) * 0.15
        senal += np.convolve(rafaga, np.ones(8) / 8, mode="same")
    pico = np.max(np.abs(senal)) or 1.0
    return vel * (0.5 if ligada else 1.0) * senal / pico


def reverb_leve(x: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    n = int(0.35 * SR)
    ir = rng.normal(size=n) * np.exp(-np.arange(n) / SR * 14)
    ir[0] = 0
    largo = len(x) + n
    cola = np.fft.irfft(np.fft.rfft(x, largo) * np.fft.rfft(ir, largo), largo)
    return x + 0.12 * cola[: len(x)] / (np.sqrt(np.sum(ir**2)) + 1e-9)


def bajo_de_fondo(duracion: float, bpm: float, rng: np.random.Generator) -> np.ndarray:
    """Línea de bajo (A2 A2 E2 G2, negras) que simula el sangrado de otra pista."""
    seg = 60.0 / bpm
    x = np.zeros(int(duracion * SR))
    ciclo = [45, 45, 40, 43]
    for i in range(int(duracion / seg)):
        nota = cuerda(ciclo[i % 4], seg * 0.9, False, 0.0, 1.0, rng)
        a = int(i * seg * SR)
        x[a : a + len(nota)] += nota[: len(x) - a]
    return x


def renderizar(caso: Caso) -> tuple[np.ndarray, list[dict]]:
    rng = np.random.default_rng(SEMILLA)
    seg_beat = 60.0 / caso.bpm
    fin = max(n.inicio_beat + n.dur_beats for n in caso.notas) * seg_beat + 1.0
    audio = np.zeros(int(fin * SR))
    verdad = []
    for nota in caso.notas:
        ini = nota.inicio_beat * seg_beat
        dur = nota.dur_beats * seg_beat * 0.95  # un respiro entre notas iguales
        for midi in nota.midis:
            onda = cuerda(midi, dur, nota.ligada, nota.bend_semitonos, nota.vel * 0.6, rng)
            a = int(ini * SR)
            audio[a : a + len(onda)] += onda[: len(audio) - a]
            verdad.append({"onset": round(ini, 4), "offset": round(ini + dur, 4), "midi": midi})
    if caso.reverb:
        audio = reverb_leve(audio, rng)
    if caso.bajo_db is not None:
        audio += bajo_de_fondo(fin, caso.bpm, rng)[: len(audio)] * 10 ** (caso.bajo_db / 20)
    if caso.ruido_db is not None:
        potencia = np.mean(audio**2)
        audio += rng.normal(size=len(audio)) * np.sqrt(potencia / 10 ** (caso.ruido_db / 10))
    audio = 0.8 * audio / np.max(np.abs(audio))
    verdad.sort(key=lambda d: (d["onset"], d["midi"]))
    return audio.astype(np.float32), verdad


def _secuencia(alturas: list[int], paso: float, repeticiones: int = 1) -> list[Nota]:
    notas, beat = [], 0.0
    for _ in range(repeticiones):
        for m in alturas:
            notas.append(Nota(beat, paso, [m]))
            beat += paso
    return notas


def casos() -> list[Caso]:
    lick = [
        57,
        60,
        62,
        64,
        62,
        60,
        57,
        55,
        57,
        60,
        64,
        67,
        64,
        62,
        60,
        57,
    ]  # A menor pentatónica
    rapido = [64, 67, 69, 67, 64, 62, 60, 62, 64, 67, 72, 69, 67, 64, 62, 60]
    power = [
        Nota(0, 1, [45, 52, 57]),
        Nota(1, 1, [45, 52, 57]),
        Nota(2, 0.5, [48, 55, 60]),
        Nota(2.5, 0.5, [50, 57, 62]),
        Nota(3, 1, [52, 59, 64]),
        Nota(4, 1, [45, 52, 57]),
        Nota(5, 1, [43, 50, 55]),
        Nota(6, 2, [40, 47, 52]),
    ]
    doble = [
        Nota(0, 1, [64, 67]),
        Nota(1, 1, [62, 65]),
        Nota(2, 0.5, [60, 64]),
        Nota(2.5, 0.5, [62, 65]),
        Nota(3, 1, [64, 69]),
        Nota(4, 1, [67, 71]),
        Nota(5, 1, [65, 69]),
        Nota(6, 2, [64, 67]),
    ]
    ligadas: list[Nota] = []
    beat = 0.0
    for base, sube in [(57, 59), (60, 62), (64, 66), (62, 64), (57, 60), (64, 67)]:
        ligadas += [
            Nota(beat, 0.5, [base]),
            Nota(beat + 0.5, 0.5, [sube], ligada=True),  # hammer-on
            Nota(beat + 1.0, 0.5, [base], ligada=True),  # pull-off
            Nota(beat + 1.5, 0.5, [sube]),
        ]
        beat += 2.0
    bends = [
        Nota(i * 2.0, 1.75, [m], bend_semitonos=2.0 if i % 2 == 0 else 1.0)
        for i, m in enumerate([64, 67, 69, 62, 64, 67])
    ]
    return [
        Caso("lento_penta_90", 90, _secuencia(lick, 0.5)),
        Caso("rapido_semicorcheas_140", 140, _secuencia(rapido, 0.25, 2)),
        Caso("power_chords", 100, power),
        Caso("double_stops", 100, doble),
        Caso("ligados", 100, ligadas),
        Caso(
            "ruido_reverb_bajo",
            100,
            _secuencia(lick, 0.5),
            ruido_db=20,
            reverb=True,
            bajo_db=-14,
        ),
        Caso("bends", 90, bends),
    ]


def generar(destino: Path = SALIDA) -> list[Caso]:
    destino.mkdir(parents=True, exist_ok=True)
    lista = casos()
    for caso in lista:
        audio, verdad = renderizar(caso)
        sf.write(destino / f"{caso.nombre}.wav", audio, SR, subtype="PCM_16")
        (destino / f"{caso.nombre}.json").write_text(
            json.dumps({"bpm": caso.bpm, "notas": verdad}, indent=1), encoding="utf-8"
        )
    return lista


if __name__ == "__main__":
    for c in generar():
        print(c.nombre)
