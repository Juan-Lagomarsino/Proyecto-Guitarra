"""Los patrones del catálogo del worker validan con los modelos de la API (esquema único)."""

import json
from pathlib import Path

import pytest

from guitarra_api.domain.notation import Strum
from guitarra_api.domain.song_chart import SectionArpeggio, SectionStrum

CATALOG = Path(__file__).resolve().parents[2] / "worker/src/guitarra_worker/strum/catalog.json"
ENTRIES = json.loads(CATALOG.read_text(encoding="utf-8"))
STRUMS = [e for e in ENTRIES if e["kind"] == "strum"]
ARPEGGIOS = [e for e in ENTRIES if e["kind"] == "arpeggio"]


@pytest.mark.parametrize("entry", STRUMS, ids=lambda e: e["id"])
def test_strum_entries_validate(entry):
    Strum.model_validate({"t": 0, "pattern": entry["pattern"], "accent": entry["accent"]})
    SectionStrum.model_validate(
        {
            "pattern": entry["pattern"],
            "accent": entry["accent"],
            "beats_per_cycle": entry["beats_per_cycle"],
            "pattern_id": entry["id"],
            "confidence": 0.5,
        }
    )


@pytest.mark.parametrize("entry", ARPEGGIOS, ids=lambda e: e["id"])
def test_arpeggio_entries_validate(entry):
    SectionArpeggio.model_validate(
        {"pattern_id": entry["id"], "pattern": entry["pattern"], "confidence": 0.5}
    )


def test_catalog_is_not_empty():
    assert STRUMS and ARPEGGIOS
