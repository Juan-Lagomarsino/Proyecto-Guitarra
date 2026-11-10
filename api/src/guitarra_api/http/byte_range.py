"""Interpreta el header `Range` de un solo rango de bytes (RFC 9110)."""

import re
from dataclasses import dataclass

_RANGE = re.compile(r"bytes=(\d*)-(\d*)")


class UnsatisfiableRangeError(Exception):
    """Rango mal formado, múltiple o fuera del archivo (se responde 416)."""


@dataclass(frozen=True)
class ByteRange:
    start: int
    end: int  # inclusive

    @property
    def length(self) -> int:
        return max(self.end - self.start + 1, 0)


def parse_range(header: str, size: int) -> ByteRange:
    match = _RANGE.fullmatch(header.strip())
    if match is None:
        raise UnsatisfiableRangeError(header)
    first, last = match.groups()
    if first:
        start = int(first)
        end = min(int(last), size - 1) if last else size - 1
    elif last:  # sufijo: los últimos N bytes
        start = max(size - int(last), 0)
        end = size - 1
    else:
        raise UnsatisfiableRangeError(header)
    if start >= size or start > end:
        raise UnsatisfiableRangeError(header)
    return ByteRange(start, end)
