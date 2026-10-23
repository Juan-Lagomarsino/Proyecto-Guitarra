"""Catálogo de patrones de rasgueo y arpegio (`catalog.json`).

Cada entrada es un compás: `pattern` de rasgueo usa `D`/`U`/`-` (una posición = una corchea) y de
arpegio usa p-i-m-a. Los campos `pattern` y `accent` salen tal cual al chart, así que tienen el
formato del esquema de notación de la API; `api/tests/test_strum_catalog_notation.py` los valida
contra esos modelos (el validador vive en un solo lugar). Acá solo se chequea lo mínimo para no
cargar un catálogo roto.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

CATALOG_PATH = Path(__file__).with_name("catalog.json")

Kind = Literal["strum", "arpeggio"]
KINDS: tuple[str, ...] = ("strum", "arpeggio")
_PATTERN_RE = {
    "strum": re.compile(r"^[DU-]+$"),
    "arpeggio": re.compile(r"^[pima](-[pima])*$"),
}


@dataclass(frozen=True)
class Pattern:
    id: str
    name: str
    kind: Kind
    beats_per_bar: int
    style: str
    complexity: int  # 1 (simple) a 4 (denso)
    pattern: str
    accent: list[int]
    beats_per_cycle: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.id,
            "pattern": self.pattern,
            "accent": list(self.accent),
            "beats_per_cycle": self.beats_per_cycle,
        }


def _parse(entry: dict[str, Any]) -> Pattern:
    try:
        pattern = Pattern(**entry)
    except TypeError as error:
        raise ValueError(f"entrada de catálogo inválida: {error}") from error
    if pattern.kind not in KINDS:
        raise ValueError(f"'{pattern.id}': tipo desconocido '{pattern.kind}'")
    if not _PATTERN_RE[pattern.kind].match(pattern.pattern):
        raise ValueError(f"'{pattern.id}': patrón inválido '{pattern.pattern}'")
    if any(not 0 <= index < len(pattern.pattern) for index in pattern.accent):
        raise ValueError(f"'{pattern.id}': 'accent' fuera del patrón")
    return pattern


def load_catalog(path: Path = CATALOG_PATH) -> list[Pattern]:
    entries = json.loads(path.read_text(encoding="utf-8"))
    patterns = [_parse(entry) for entry in entries]
    ids = [pattern.id for pattern in patterns]
    if len(set(ids)) != len(ids):
        raise ValueError("el catálogo tiene ids repetidos")
    return patterns
