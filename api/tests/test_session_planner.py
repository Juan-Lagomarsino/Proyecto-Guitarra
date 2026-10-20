import random

from guitarra_api.domain.session_planner import (
    BLOCK_ORDER,
    ExerciseInfo,
    build_session,
    current_level,
    is_pending,
)


def ex(id_, level, category, minutes=5, bpm=100, type_="scale"):
    return ExerciseInfo(
        id=id_,
        level_order=level,
        type=type_,
        category=category,
        duration_min=minutes,
        bpm_target=bpm,
    )


def full_level(level, minutes=5):
    return [ex(f"l{level}-{c}", level, c, minutes) for c in BLOCK_ORDER]


def ids(plan):
    return [e.exercise.id for b in plan.blocks for e in b.exercises]


def wide_curriculum(minutes=5, n=8):
    return [ex(f"x{i}-{c}", 1, c, minutes) for i in range(n) for c in BLOCK_ORDER]


def test_pending_rules():
    e = ex("a", 1, "warmup", bpm=100)
    assert is_pending(e, {})
    assert is_pending(e, {"a": 90})
    assert not is_pending(e, {"a": 100})
    assert not is_pending(ex("b", 1, "riff", bpm=None), {"b": 1})
    assert is_pending(ex("c", 1, "riff", bpm=None), {})


def test_current_level():
    curriculum = full_level(1) + full_level(2)
    assert current_level(curriculum, {}) == 1
    assert current_level(curriculum, {e.id: 1 for e in full_level(1)}) == 2
    assert current_level(curriculum, {e.id: 1 for e in curriculum}) is None
    assert current_level([], {}) is None


def test_empty_curriculum():
    plan = build_session([], {}, seed=1)
    assert plan.blocks == []
    assert plan.total_minutes == 0


def test_blocks_in_order_and_duration_in_range():
    plan = build_session(full_level(1) + full_level(2), {}, seed=1)
    assert [b.category for b in plan.blocks] == list(BLOCK_ORDER)
    assert 15 <= plan.total_minutes <= 25
    assert plan.total_minutes == sum(e.minutes for b in plan.blocks for e in b.exercises)


def test_total_minutes_range_for_many_seeds():
    curriculum = [
        ex(f"l{lvl}-{c}-{i}", lvl, c, minutes=3 + i)
        for lvl in range(1, 4)
        for c in BLOCK_ORDER
        for i in range(4)
    ]
    for seed in range(30):
        plan = build_session(curriculum, {}, seed=seed)
        assert 15 <= plan.total_minutes <= 25
        assert [b.category for b in plan.blocks] == list(BLOCK_ORDER)


def test_deterministic_same_seed_regardless_of_input_order():
    curriculum = wide_curriculum(minutes=2, n=6)
    a = build_session(curriculum, {}, seed=42)
    b = build_session(list(reversed(curriculum)), {}, seed=42)
    assert a == b


def test_different_seed_gives_different_combination():
    curriculum = wide_curriculum()
    results = {tuple(ids(build_session(curriculum, {}, seed=s))) for s in range(10)}
    assert len(results) > 1


def test_no_alternatives_same_result_for_any_seed():
    curriculum = full_level(1)
    assert ids(build_session(curriculum, {}, 1)) == ids(build_session(curriculum, {}, 2))


def test_does_not_use_global_random():
    curriculum = wide_curriculum()
    random.seed(1)
    a = build_session(curriculum, {}, seed=5)
    random.seed(999)
    b = build_session(curriculum, {}, seed=5)
    assert a == b


def test_does_not_alter_global_random_state():
    random.seed(7)
    expected = random.random()
    random.seed(7)
    build_session(wide_curriculum(), {}, seed=5)
    assert random.random() == expected


def test_prefers_pending_of_current_level():
    plan = build_session(full_level(1) + full_level(2), {}, seed=3)
    assert all(e.exercise.level_order == 1 for b in plan.blocks for e in b.exercises)


def test_skips_completed_exercises_of_current_level():
    level = [ex(f"t{i}", 1, "technique", 5) for i in range(3)]
    plan = build_session(level, {"t0": 100, "t1": 100}, seed=1)
    assert ids(plan)[0] == "t2"  # lo pendiente va antes que el repaso


def test_bpm_below_target_is_pending():
    level = [ex("t0", 1, "technique", 5, bpm=120), ex("t1", 1, "technique", 5, bpm=120)]
    plan = build_session(level, {"t0": 80, "t1": 120}, seed=1)
    assert ids(plan)[0] == "t0"


def test_warmup_can_come_from_completed_previous_level():
    level1 = full_level(1)
    level2 = [e for e in full_level(2) if e.category != "warmup"]
    history = {e.id: 100 for e in level1}
    plan = build_session(level1 + level2, history, seed=1)
    warm = plan.blocks[0]
    assert warm.category == "warmup"
    assert [e.exercise.id for e in warm.exercises] == ["l1-warmup"]
    assert all(e.exercise.level_order == 2 for b in plan.blocks[1:] for e in b.exercises)


def test_warmup_pending_of_current_level_beats_completed_earlier_ones():
    old = [ex(f"old{i}", 1, "warmup", 5) for i in range(3)]
    now = [ex("now", 2, "warmup", 5), ex("tech", 2, "technique", 5)]
    history = {e.id: 100 for e in old}
    for seed in range(20):
        plan = build_session(old + now, history, seed=seed)
        assert plan.blocks[0].exercises[0].exercise.id == "now"


def test_short_exercises_keep_all_four_blocks_in_order():
    curriculum = [ex(f"t{i}", 1, "technique", 2) for i in range(10)]
    curriculum += [ex("w", 1, "warmup", 2), ex("r", 1, "riff", 2), ex("i", 1, "improvisation", 2)]
    for seed in range(20):
        plan = build_session(curriculum, {}, seed=seed)
        assert [b.category for b in plan.blocks] == list(BLOCK_ORDER)


def test_everything_completed_still_builds_review_session():
    curriculum = full_level(1) + full_level(2)
    plan = build_session(curriculum, {e.id: 999 for e in curriculum}, seed=1)
    assert [b.category for b in plan.blocks] == list(BLOCK_ORDER)
    assert 15 <= plan.total_minutes <= 25


def test_missing_block_is_completed_with_other_category_within_time():
    curriculum = [e for e in full_level(1, minutes=4) if e.category != "riff"]
    curriculum += [ex(f"extra{i}", 1, "technique", 4) for i in range(4)]
    plan = build_session(curriculum, {}, seed=1)
    assert 15 <= plan.total_minutes <= 25
    assert len(set(ids(plan))) == len(ids(plan))


def test_level_with_only_one_category_fills_session():
    curriculum = [ex(f"t{i}", 1, "technique", 5) for i in range(6)]
    plan = build_session(curriculum, {}, seed=1)
    assert 15 <= plan.total_minutes <= 25
    assert len(set(ids(plan))) == len(ids(plan))


def test_never_exceeds_max_with_long_exercises():
    curriculum = [ex(f"l{i}-{c}", 1, c, 12) for i in range(3) for c in BLOCK_ORDER]
    plan = build_session(curriculum, {}, seed=1)
    assert 0 < plan.total_minutes <= 25


def test_exercise_longer_than_limit_is_skipped():
    curriculum = [ex("huge", 1, "technique", 60), ex("ok", 1, "warmup", 5)]
    assert ids(build_session(curriculum, {}, seed=1)) == ["ok"]


def test_custom_target_minutes():
    plan = build_session(wide_curriculum(minutes=2, n=10), {}, seed=1, target_minutes=10)
    assert 5 <= plan.total_minutes <= 15
