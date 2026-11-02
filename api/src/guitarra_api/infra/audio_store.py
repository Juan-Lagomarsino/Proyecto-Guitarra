"""Almacenamiento del audio en disco: `<raíz>/<song_id>/<kind>.<format>` con reemplazo atómico."""

import os
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


class AudioTooLargeError(Exception):
    def __init__(self, max_bytes: int) -> None:
        super().__init__(f"El audio supera el tope de {max_bytes} bytes")
        self.max_bytes = max_bytes


@dataclass(frozen=True)
class StoredAudio:
    relative_path: str
    size: int


class PendingAudio:
    """Escritura en curso a un archivo temporal; `commit` lo renombra sobre el destino."""

    def __init__(self, target: Path, relative_path: str, max_bytes: int) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(dir=target.parent, suffix=".part")
        self._file: BinaryIO = os.fdopen(descriptor, "wb")
        self._temp = Path(temp_name)
        self._target = target
        self._relative_path = relative_path
        self._max_bytes = max_bytes
        self._size = 0

    @property
    def size(self) -> int:
        return self._size

    def write(self, chunk: bytes) -> None:
        self._size += len(chunk)
        if self._size > self._max_bytes:
            raise AudioTooLargeError(self._max_bytes)
        self._file.write(chunk)

    def commit(self) -> StoredAudio:
        self._file.close()
        self._temp.replace(self._target)  # atómico en el mismo volumen
        return StoredAudio(self._relative_path, self._size)

    def abort(self) -> None:
        self._file.close()
        self._temp.unlink(missing_ok=True)


class AudioStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def begin(self, song_id: int, kind: str, audio_format: str, max_bytes: int) -> PendingAudio:
        relative = f"{song_id}/{kind}.{audio_format}"
        return PendingAudio(self.resolve(relative), relative, max_bytes)

    def save(
        self, song_id: int, kind: str, audio_format: str, chunks: Iterable[bytes], max_bytes: int
    ) -> StoredAudio:
        pending = self.begin(song_id, kind, audio_format, max_bytes)
        try:
            for chunk in chunks:
                pending.write(chunk)
        except BaseException:
            pending.abort()
            raise
        return pending.commit()

    def resolve(self, relative_path: str) -> Path:
        root = self._root.resolve()
        path = (root / relative_path).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"Ruta fuera de la carpeta de audio: {relative_path}")
        return path

    def remove(self, relative_path: str) -> None:
        self.resolve(relative_path).unlink(missing_ok=True)
