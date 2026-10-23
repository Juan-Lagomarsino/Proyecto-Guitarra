import json
import re
from pathlib import Path

import pytest

from guitarra_worker.strum.catalog import load_catalog

STRUM_RE = re.compile(r"^[DU-]+$")
ARPEGGIO_RE = re.compile(r"^[pima](-[pima])*$")


def test_ids_are_unique_and_kinds_known():
    patterns = load_catalog()
    ids = [p.id for p in patterns]
    assert len(set(ids)) == len(ids)
    assert {p.kind for p in patterns} == {"strum", "arpeggio"}


def test_patterns_follow_the_notation_format():
    for p in load_catalog():
        if p.kind == "strum":
            assert STRUM_RE.match(p.pattern)
            assert all(0 <= i < len(p.pattern) for i in p.accent)
            assert p.beats_per_cycle == p.beats_per_bar
        else:
            assert ARPEGGIO_RE.match(p.pattern)
            assert p.accent == []


def test_every_bar_has_strum_and_arpeggio_options():
    patterns = load_catalog()
    for bar in (3, 4):
        for kind in ("strum", "arpeggio"):
            assert [p for p in patterns if p.kind == kind and p.beats_per_bar == bar]


def test_invalid_entry_is_rejected(tmp_path: Path):
    bad = tmp_path / "c.json"
    entry = {"id": "x", "name": "x", "kind": "strum", "beats_per_bar": 4, "style": "s"}
    entry |= {"complexity": 1, "pattern": "XX", "accent": []}
    bad.write_text(json.dumps([entry]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_catalog(bad)
