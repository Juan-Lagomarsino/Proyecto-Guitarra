"""Autosimilitud del audio con librosa (chroma + MFCC sincronizados a beats).

librosa se importa recién al usarlo: los tests y el resto del worker no lo necesitan.
"""

from pathlib import Path

import numpy as np

SAMPLE_RATE = 22050
MFCC_WEIGHT = 0.5
N_MFCC = 13
RECURRENCE_WIDTH = 3  # beats vecinos que no cuentan como repetición
SMOOTHING_SIZE = 3


class LibrosaSelfSimilarity:
    def self_similarity(self, wav_path: Path, beats: np.ndarray) -> np.ndarray:
        import librosa
        import scipy.ndimage

        y, sr = librosa.load(str(wav_path), sr=SAMPLE_RATE, mono=True)
        features = self._beat_features(librosa, y, sr, beats)
        ssm = librosa.segment.recurrence_matrix(
            features, mode="affinity", sym=True, width=RECURRENCE_WIDTH
        )
        return scipy.ndimage.uniform_filter(ssm, size=(SMOOTHING_SIZE, SMOOTHING_SIZE))

    @staticmethod
    def _beat_features(librosa, y: np.ndarray, sr: int, beats: np.ndarray) -> np.ndarray:
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC)
        frames = librosa.time_to_frames(beats, sr=sr)

        def sync(matrix: np.ndarray) -> np.ndarray:
            # sync agrega un tramo antes del primer beat: la columna i+1 arranca en el beat i.
            return librosa.util.sync(matrix, frames, aggregate=np.median)[:, 1 : len(beats) + 1]

        timbre = librosa.util.normalize(mfcc[1:], axis=1)
        return np.vstack(
            [
                librosa.util.normalize(sync(chroma), axis=0),
                MFCC_WEIGHT * librosa.util.normalize(sync(timbre), axis=0),
            ]
        )
