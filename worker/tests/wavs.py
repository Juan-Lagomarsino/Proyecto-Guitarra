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


def make_click_wav(
    path: Path,
    bpm: float,
    seconds: float,
    rate: int = 48_000,
    beats_per_bar: int = 4,
    offset_s: float = 0.5,
) -> Path:
    """WAV mono con un click por beat (más grave y fuerte el primero de cada compás)."""
    frames = int(seconds * rate)
    samples = [0] * frames
    click_len = int(0.03 * rate)
    beat_s = 60.0 / bpm
    beat = 0
    while (start := int((offset_s + beat * beat_s) * rate)) < frames:
        accent = beat % beats_per_bar == 0
        freq, amp = (800, 24000) if accent else (1600, 14000)
        for i in range(min(click_len, frames - start)):
            decay = 1 - i / click_len
            samples[start + i] = int(amp * decay * math.sin(2 * math.pi * freq * i / rate))
        beat += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(struct.pack(f"<{frames}h", *samples))
    return path
