"""Helper de tests: genera WAVs sintéticos."""

import math
import struct
import wave
from pathlib import Path


def make_wav(path: Path, seconds: float = 1.0, rate: int = 44_100, channels: int = 1) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        frames = int(seconds * rate)
        samples = (int(8000 * math.sin(2 * math.pi * 440 * i / rate)) for i in range(frames))
        wav.writeframes(b"".join(struct.pack("<h", s) * channels for s in samples))
    return path
