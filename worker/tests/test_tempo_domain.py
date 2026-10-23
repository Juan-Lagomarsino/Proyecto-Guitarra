import pytest

from guitarra_worker.domain.tempo import analyze_beats, beats_per_bar, bpm_from_beats


def click_beats(bpm: float, n: int, start: float = 0.5) -> list[float]:
    return [start + i * 60.0 / bpm for i in range(n)]


def test_bpm_from_regular_beats():
    assert bpm_from_beats(click_beats(120, 20)) == pytest.approx(120, abs=0.01)


def test_bpm_ignores_an_outlier_gap():
    beats = click_beats(100, 20)
    beats[10] += 0.05  # un beat corrido: dos intervalos raros, la mediana no se entera
    assert bpm_from_beats(beats) == pytest.approx(100, abs=0.01)


def test_bpm_averages_out_the_20ms_frame_quantization():
    exact = click_beats(140, 70, start=0.0)
    quantized = [round(t / 0.02) * 0.02 for t in exact]  # lo que devuelve el modelo (50 fps)
    assert bpm_from_beats(quantized) == pytest.approx(140, abs=0.5)


def test_bpm_ignores_a_missed_beat():
    beats = click_beats(100, 20)
    del beats[8]  # un intervalo del doble
    assert bpm_from_beats(beats) == pytest.approx(100, abs=0.01)


def test_bpm_needs_two_beats():
    assert bpm_from_beats([]) is None
    assert bpm_from_beats([1.0]) is None


def test_beats_per_bar_four_four():
    beats = click_beats(120, 16)
    assert beats_per_bar(beats, beats[::4]) == 4


def test_beats_per_bar_three_four_with_jittered_downbeats():
    beats = click_beats(90, 18)
    downbeats = [t + 0.004 for t in beats[::3]]
    assert beats_per_bar(beats, downbeats) == 3


def test_beats_per_bar_uses_the_most_common_bar_length():
    beats = click_beats(120, 20)
    downbeats = [beats[i] for i in (0, 4, 8, 11, 15)]  # un compás de 3 entre cuatro de 4
    assert beats_per_bar(beats, downbeats) == 4


def test_beats_per_bar_without_enough_downbeats():
    beats = click_beats(120, 8)
    assert beats_per_bar(beats, []) is None
    assert beats_per_bar(beats, [beats[0]]) is None


def test_analyze_beats_full_result():
    beats = click_beats(120, 16, start=1.0)
    result = analyze_beats(beats, beats[2::4])
    assert result["bpm"] == pytest.approx(120, abs=0.01)
    assert result["beats_per_bar"] == 4
    assert result["beats"] == pytest.approx(beats)
    assert result["downbeats"] == pytest.approx(beats[2::4])
    assert result["first_downbeat_s"] == pytest.approx(beats[2])
    assert result["first_beat_s"] == pytest.approx(1.0)


def test_analyze_beats_without_beats_is_an_empty_result_not_an_error():
    result = analyze_beats([], [])
    assert result["bpm"] is None
    assert result["beats_per_bar"] is None
    assert result["beats"] == []
    assert result["downbeats"] == []
    assert result["first_downbeat_s"] is None
