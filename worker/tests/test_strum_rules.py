from guitarra_worker.strum.catalog import load_catalog
from guitarra_worker.strum.rules import (
    attacks_per_beat,
    candidate_patterns,
    default_pattern,
    max_complexity_for,
)

CATALOG = load_catalog()


def test_3_4_never_gets_4_4_patterns():
    found = candidate_patterns(CATALOG, "strum", beats_per_bar=3, bpm=100)
    assert found
    assert all(p.beats_per_bar == 3 for p in found)


def test_4_4_never_gets_3_4_patterns():
    found = candidate_patterns(CATALOG, "arpeggio", beats_per_bar=4, bpm=100)
    assert found
    assert all(p.beats_per_bar == 4 for p in found)


def test_unsupported_bar_has_no_candidates():
    assert candidate_patterns(CATALOG, "strum", beats_per_bar=7, bpm=100) == []


def test_max_complexity_decreases_with_tempo():
    levels = [max_complexity_for(bpm) for bpm in (60, 100, 130, 160, 200)]
    assert levels == sorted(levels, reverse=True)
    assert levels[0] > levels[-1]


def test_fast_tempo_gets_simpler_patterns_than_slow():
    slow = candidate_patterns(CATALOG, "strum", beats_per_bar=4, bpm=70)
    fast = candidate_patterns(CATALOG, "strum", beats_per_bar=4, bpm=190)
    assert max(p.complexity for p in fast) < max(p.complexity for p in slow)
    assert max(p.complexity for p in fast) <= max_complexity_for(190)


def test_very_fast_tempo_still_has_the_simplest_pattern():
    found = candidate_patterns(CATALOG, "strum", beats_per_bar=4, bpm=400)
    assert found
    assert min(p.complexity for p in found) == 1


def test_default_pattern_is_among_candidates_and_deterministic():
    found = candidate_patterns(CATALOG, "strum", beats_per_bar=4, bpm=100)
    assert default_pattern(found) in found
    assert default_pattern(found) == default_pattern(list(reversed(found)))


def test_default_pattern_follows_attack_density_when_given():
    found = candidate_patterns(CATALOG, "strum", beats_per_bar=4, bpm=80)
    sparse = default_pattern(found, density=1.0)
    dense = default_pattern(found, density=3.5)
    assert attacks_per_beat(sparse) < attacks_per_beat(dense)


def test_default_pattern_of_nothing_is_none():
    assert default_pattern([]) is None


def test_attacks_per_beat_counts_only_hits():
    pattern = next(p for p in CATALOG if p.pattern == "D-D-D-D-")
    assert attacks_per_beat(pattern) == 1.0
