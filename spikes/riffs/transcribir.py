"""Los dos candidatos. Ambos devuelven un array (N, 3) con columnas onset s, offset s, midi."""

import logging
from pathlib import Path

import librosa
import numpy as np
from scipy.ndimage import median_filter

logging.disable(logging.WARNING)  # basic-pitch avisa de TF/CoreML/TFLite que no usamos

# Umbrales elegidos con el barrido de medir.py (ver docs/adr/0017-transcripcion-de-riffs.md)
BP_UMBRALES = {
    "onset_threshold": 0.7,
    "frame_threshold": 0.4,
    "minimum_note_length": 58.0,
}

_modelo = None


def _modelo_onnx():
    """Carga el modelo ONNX que trae el paquete (sin TensorFlow). Una sola vez por proceso."""
    global _modelo
    if _modelo is None:
        from basic_pitch.inference import ICASSP_2022_MODEL_PATH, Model

        _modelo = Model(ICASSP_2022_MODEL_PATH)
    return _modelo


def basic_pitch_notas(audio: Path, **umbrales: float) -> np.ndarray:
    from basic_pitch.inference import predict

    params = {**BP_UMBRALES, **umbrales}
    _, _, eventos = predict(audio, _modelo_onnx(), **params)
    # evento = (inicio, fin, midi, amplitud, bends)
    notas = [(e[0], e[1], e[2]) for e in eventos]
    return np.array(sorted(notas), dtype=float).reshape(-1, 3)


# --- pYIN: f0 por cuadro -> notas ------------------------------------------------------------
PYIN_SR = 22_050
PYIN_HOP = 256  # 11,6 ms
PYIN_MIN_NOTA = 0.05  # s
PYIN_SUAVIZADO = 5  # cuadros del filtro de mediana sobre la altura


def pyin_notas(audio: Path, delta_onset: float = 0.08) -> np.ndarray:
    """Segmenta f0 en notas.

    1. pYIN da f0 por cuadro (C2..C6) y la marca de cuadro sonoro.
    2. Altura en MIDI redondeada con filtro de mediana (quita saltos de octava de 1 cuadro).
    3. Un corte de nota ocurre donde (a) cambia la altura redondeada o (b) hay un onset de
       energía (`librosa.onset.onset_detect`) o (c) se pierde el sonoro.
    4. Cada tramo sonoro >= 50 ms es una nota con su mediana de altura.
    """
    y, sr = librosa.load(audio, sr=PYIN_SR, mono=True)
    f0, sonoro, _ = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C6"),
        sr=sr,
        frame_length=2048,
        hop_length=PYIN_HOP,
    )
    midi = np.where(sonoro, librosa.hz_to_midi(np.nan_to_num(f0, nan=440.0)), np.nan)
    relleno = np.where(np.isnan(midi), 0.0, midi)
    altura = np.round(median_filter(relleno, size=PYIN_SUAVIZADO)).astype(int)
    altura[~sonoro] = 0

    onsets = set(
        librosa.onset.onset_detect(
            y=y,
            sr=sr,
            hop_length=PYIN_HOP,
            delta=delta_onset,
            units="frames",
            backtrack=False,
        ).tolist()
    )
    notas, inicio = [], None
    for i in range(len(altura) + 1):
        fin_tramo = (
            i == len(altura)
            or altura[i] == 0
            or (inicio is not None and (altura[i] != altura[inicio] or i in onsets))
        )
        if inicio is not None and fin_tramo:
            t0 = librosa.frames_to_time(inicio, sr=sr, hop_length=PYIN_HOP)
            t1 = librosa.frames_to_time(i, sr=sr, hop_length=PYIN_HOP)
            if t1 - t0 >= PYIN_MIN_NOTA:
                notas.append((t0, t1, float(np.median(altura[inicio:i]))))
            inicio = None
        if i < len(altura) and altura[i] != 0 and inicio is None:
            inicio = i
    return np.array(notas, dtype=float).reshape(-1, 3)
