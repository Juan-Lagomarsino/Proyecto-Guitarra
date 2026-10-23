import numpy as np
import pytest

from guitarra_worker.domain.structure import (
    analyze_structure,
    detect_boundaries,
    snap_to_downbeats,
)

BEATS_PER_BAR = 4
BEAT_S = 0.5  # 120 BPM, compás de 2 s


def build_song(layout: str, bars_per_section: int | dict[str, int] = 8):
    """Matriz de autosimilitud ideal (1 si la sección es la misma) y grilla de beats."""
    labels = []
    for letter in layout:
        bars = bars_per_section[letter] if isinstance(bars_per_section, dict) else bars_per_section
        labels += [letter] * bars * BEATS_PER_BAR
    arr = np.array(labels)
    ssm = (arr[:, None] == arr[None, :]).astype(float)
    beats = np.arange(len(labels)) * BEAT_S
    downbeats = beats[::BEATS_PER_BAR]
    return ssm, beats, downbeats, len(labels) * BEAT_S


def names_of(result):
    return [s.name for s in result.sections]


def test_detecta_los_limites_de_a_b_a_b_c_b():
    ssm, *_ = build_song("ABABCB")
    assert detect_boundaries(ssm, BEATS_PER_BAR) == [32, 64, 96, 128, 160]


def test_secciones_con_inicio_fin_y_orden_alineadas_a_compases():
    ssm, beats, downbeats, duration = build_song("ABABCB")
    result = analyze_structure(ssm, beats, downbeats, duration)
    assert [s.order for s in result.sections] == [0, 1, 2, 3, 4, 5]
    assert result.sections[0].start_s == 0.0
    assert result.sections[-1].end_s == duration
    for prev, nxt in zip(result.sections, result.sections[1:], strict=False):
        assert prev.end_s == nxt.start_s
    for section in result.sections:
        assert section.start_s % 2.0 == 0.0  # empieza en un downbeat
        assert section.end_bar - section.start_bar == 8


def test_nombres_heuristicos_segun_repeticion():
    ssm, beats, downbeats, duration = build_song("ABABCB")
    result = analyze_structure(ssm, beats, downbeats, duration)
    assert names_of(result) == [
        "estrofa",
        "estribillo",
        "estrofa",
        "estribillo",
        "puente",
        "estribillo",
    ]
    assert [s.group for s in result.sections] == ["A", "B", "A", "B", "C", "B"]


def test_intro_y_final_son_secciones_unicas_en_los_extremos():
    ssm, beats, downbeats, duration = build_song("IABABF", {"I": 4, "A": 8, "B": 8, "F": 4})
    result = analyze_structure(ssm, beats, downbeats, duration)
    assert names_of(result) == [
        "intro",
        "estrofa",
        "estribillo",
        "estrofa",
        "estribillo",
        "final",
    ]


def test_cancion_sin_repeticiones_deja_las_secciones_sin_nombre():
    ssm, beats, downbeats, duration = build_song("ABCD")
    result = analyze_structure(ssm, beats, downbeats, duration)
    assert len(result.sections) == 4
    assert names_of(result) == [None] * 4
    assert result.confidence == "baja"


def test_cancion_muy_corta_es_una_sola_seccion():
    ssm, beats, downbeats, duration = build_song("AB", 2)
    result = analyze_structure(ssm, beats, downbeats, duration)
    assert len(result.sections) == 1
    assert result.sections[0].start_s == 0.0
    assert result.sections[0].end_s == duration
    assert result.sections[0].name is None


def test_sin_beats_no_hay_secciones():
    result = analyze_structure(np.zeros((0, 0)), np.array([]), np.array([]), 0.0)
    assert result.sections == []


def test_limites_se_ajustan_al_downbeat_mas_cercano_sin_duplicados():
    downbeats = np.array([0.0, 2.0, 4.0, 6.0, 8.0])
    snapped = snap_to_downbeats(np.array([1.8, 2.3, 5.1]), downbeats)
    assert snapped.tolist() == [2.0, 6.0]


@pytest.mark.parametrize("layout", ["A", "AA"])
def test_una_sola_seccion_no_tiene_limites(layout):
    ssm, *_ = build_song(layout, 16)
    assert detect_boundaries(ssm, BEATS_PER_BAR) == []


def test_duracion_menor_al_ultimo_inicio_no_deja_secciones_vacias():
    ssm, beats, downbeats, _ = build_song("ABABCB")
    duration = 150.0  # corta antes del inicio de la última sección (160 s)
    result = analyze_structure(ssm, beats, downbeats, duration)
    assert all(s.start_s < s.end_s for s in result.sections)
    assert result.sections[-1].end_s == duration


def test_empate_de_repeticiones_elige_estribillo_al_grupo_que_aparece_mas_tarde():
    ssm, beats, downbeats, duration = build_song("ABAB")
    result = analyze_structure(ssm, beats, downbeats, duration)
    assert names_of(result) == ["estrofa", "estribillo", "estrofa", "estribillo"]


def test_mas_repeticiones_gana_sobre_aparecer_mas_tarde():
    ssm, beats, downbeats, duration = build_song("ABACABA")
    result = analyze_structure(ssm, beats, downbeats, duration)
    assert names_of(result) == [
        "estribillo",
        "estrofa",
        "estribillo",
        "puente",
        "estribillo",
        "estrofa",
        "estribillo",
    ]
