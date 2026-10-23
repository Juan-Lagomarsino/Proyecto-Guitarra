"""Lectura del catálogo de rasgueos y arpegios (`catalog.json`, compartido con el worker)."""

import json
from pathlib import Path
from typing import Any


def load_strum_catalog(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))
