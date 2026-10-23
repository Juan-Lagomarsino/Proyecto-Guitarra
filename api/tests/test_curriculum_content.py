"""Contenido del currículum: valida esquema y corrección musical, sin base de datos."""

import json
from pathlib import Path

import pytest

from guitarra_api.domain.notation import Notation
from guitarra_api.infra.curriculum_loader import CurriculumError, read_curriculum

CURRICULUM_DIR = Path(__file__).resolve().parents[2] / "curriculum"
SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MIDI_BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
CATEGORIES = {"warmup", "technique", "riff", "improvisation"}


def midi(note: str) -> int:
    """`E2` -> 40. Acepta # y b."""
    pitch = MIDI_BASE[note[0]]
    if len(note) == 3:
        pitch += 1 if note[1] == "#" else -1
    return pitch + 12 * (int(note[-1]) + 1)


def pitch_class(value: int) -> str:
    return SHARP_NAMES[value % 12]


def fretted_pitch(notation: Notation, string: int, fret: int) -> int:
    return midi(notation.tuning[6 - string]) + fret


def all_exercises():
    levels = read_curriculum(CURRICULUM_DIR)
    return [
        pytest.param(ex, id=ex.slug)
        for level in levels
        for lesson in level.lessons
        for ex in lesson.exercises
    ]


@pytest.fixture(scope="module")
def levels():
    return read_curriculum(CURRICULUM_DIR)


def test_el_primer_nivel_es_de_electrica(levels):
    assert levels[0].position == 1
    assert levels[0].instrument == "electric"


def test_nivel_1_tiene_entre_3_y_4_lecciones_y_8_a_12_ejercicios(levels):
    level = levels[0]
    total = sum(len(lesson.exercises) for lesson in level.lessons)
    assert 3 <= len(level.lessons) <= 4
    assert 8 <= total <= 12
    assert all(lesson.content_md.strip() for lesson in level.lessons)


def test_nivel_1_cubre_las_cuatro_categorias(levels):
    found = {ex.category for lesson in levels[0].lessons for ex in lesson.exercises}
    assert found == CATEGORIES


def _level_exercises(level):
    return [ex for lesson in level.lessons for ex in lesson.exercises]


def _level_by_position(levels, position):
    return next(level for level in levels if level.position == position)


def test_hay_tres_niveles_en_orden(levels):
    assert [level.position for level in levels][:3] == [1, 2, 3]
    assert all(level.instrument == "electric" for level in levels)


@pytest.mark.parametrize("position", [1, 2, 3])
def test_cada_nivel_tiene_3_lecciones_con_teoria_y_3_categorias(levels, position):
    level = _level_by_position(levels, position)
    assert len(level.lessons) >= 3
    assert all(lesson.content_md.strip() for lesson in level.lessons)
    assert len({ex.category for ex in _level_exercises(level)}) >= 3


@pytest.mark.parametrize("position", [1, 2, 3])
def test_las_escalas_de_cada_nivel_marcan_la_tonica(levels, position):
    for ex in _level_exercises(_level_by_position(levels, position)):
        if ex.type == "scale":
            assert ex.notation.tonic is not None, ex.slug


def test_nivel_2_es_pentatonica_menor_y_tiene_las_dos_cajas(levels):
    level = _level_by_position(levels, 2)
    scales = [ex for ex in _level_exercises(level) if ex.type == "scale"]
    assert len(scales) >= 3
    assert {ex.notation.tonic for ex in scales} == {"A"}
    assert any("caja-1" in ex.slug for ex in scales)
    assert any("caja-2" in ex.slug for ex in scales)


def test_nivel_2_cada_nota_de_las_escalas_es_de_la_pentatonica_menor(levels):
    for ex in _level_exercises(_level_by_position(levels, 2)):
        if ex.type != "scale":
            continue
        tonic = midi(f"{ex.notation.tonic}0") % 12
        allowed = {(tonic + step) % 12 for step in (0, 3, 5, 7, 10)}
        for event in ex.notation.events:
            value = fretted_pitch(ex.notation, event.string, event.fret) % 12
            assert value in allowed, f"{ex.slug}: {pitch_class(value)} fuera de la pentatónica"


def test_nivel_2_las_cajas_estan_en_su_posicion(levels):
    level = _level_by_position(levels, 2)
    for ex in _level_exercises(level):
        if "caja-1" in ex.slug and ex.type == "scale":
            assert {e.fret for e in ex.notation.events} <= {5, 7, 8}, ex.slug
        if "caja-2" in ex.slug and ex.type == "scale":
            assert {e.fret for e in ex.notation.events} <= {7, 8, 9, 10}, ex.slug


TWO_NOTE_TECHNIQUES = {"h": 1, "/": 1, "p": -1, "\\": -1}


def _previous_on_string(events, index):
    event = events[index]
    earlier = [other for other in events if other.string == event.string and other.t < event.t]
    return max(earlier, key=lambda other: other.t) if earlier else None


def test_nivel_3_tiene_ligados_de_los_tres_tipos(levels):
    used = {
        e.technique
        for ex in _level_exercises(_level_by_position(levels, 3))
        for e in ex.notation.events
    }
    assert {"h", "p"} <= used
    assert used & {"/", "\\"}


def test_nivel_3_los_ligados_van_en_la_nota_de_destino_con_origen_en_la_cuerda(levels):
    for ex in _level_exercises(_level_by_position(levels, 3)):
        events = sorted(ex.notation.events, key=lambda e: e.t)
        for index, event in enumerate(events):
            if event.technique not in TWO_NOTE_TECHNIQUES:
                continue
            origin = _previous_on_string(events, index)
            assert origin is not None, f"{ex.slug}: {event.technique} sin origen en t={event.t}"
            direction = TWO_NOTE_TECHNIQUES[event.technique]
            assert (event.fret - origin.fret) * direction > 0, (
                f"{ex.slug}: {event.technique} de {origin.fret} a {event.fret} en t={event.t}"
            )


def test_slugs_unicos(levels):
    slugs = [ex.slug for level in levels for lesson in level.lessons for ex in lesson.exercises]
    assert len(slugs) == len(set(slugs))


@pytest.mark.parametrize("exercise", all_exercises())
def test_tempos_y_duracion_razonables(exercise):
    assert 40 <= exercise.bpm_start <= exercise.bpm_target <= 200
    assert 2 <= exercise.duration_min <= 10
    assert exercise.notation.bpm == exercise.bpm_start


@pytest.mark.parametrize("exercise", all_exercises())
def test_cada_power_chord_tiene_tonica_y_quinta(exercise):
    notation = exercise.notation
    roots = set()
    for chord in notation.chords:
        played = [(6 - index, fret) for index, fret in enumerate(chord.shape) if fret != "x"]
        pitches = [fretted_pitch(notation, string, fret) for string, fret in played]
        root = pitches[0]  # la nota más grave del acorde
        assert len(pitches) >= 2
        assert pitches == sorted(pitches), f"{chord.name}: notas fuera de orden"
        assert chord.name == f"{pitch_class(root)}5", f"{exercise.slug}: nombre {chord.name}"
        assert pitches[1] - root == 7, f"{exercise.slug}: {chord.name} sin quinta sobre la tónica"
        for extra in pitches[2:]:
            assert (extra - root) % 12 in (0, 7), f"{exercise.slug}: {chord.name} nota ajena"
        roots.add(pitch_class(root))
    if roots:
        assert notation.tonic in roots, (
            f"{exercise.slug}: tonic {notation.tonic} no está en {roots}"
        )


@pytest.mark.parametrize("exercise", all_exercises())
def test_las_notas_sueltas_caen_en_las_pentatonicas_de_la_tonica(exercise):
    notation = exercise.notation
    if not notation.events or notation.tonic is None:
        return
    tonic = midi(f"{notation.tonic}0") % 12
    minor = {(tonic + step) % 12 for step in (0, 3, 5, 7, 10)}
    major = {(tonic + step) % 12 for step in (0, 2, 4, 7, 9)}
    for event in notation.events:
        value = fretted_pitch(notation, event.string, event.fret) % 12
        assert value in minor | major, f"{exercise.slug}: {pitch_class(value)} fuera de tonalidad"


@pytest.mark.parametrize("exercise", all_exercises())
def test_riffs_sin_acordes_empiezan_en_la_tonica(exercise):
    notation = exercise.notation
    if notation.tonic is None or notation.chords or not notation.events:
        return
    first = min(notation.events, key=lambda event: (event.t, event.string * -1))
    value = fretted_pitch(notation, first.string, first.fret)
    assert pitch_class(value) == notation.tonic


def _write_level(directory: Path, name: str, slug: str, position: int, notation: str) -> None:
    exercise = {
        "slug": slug, "title": "E", "description": "Qué tocar.", "type": "riff", "category": "riff",
        "bpm_start": 60, "bpm_target": 80, "duration_min": 3,
        "notation": json.loads(notation),
    }  # fmt: skip
    data = {
        "level": {
            "slug": f"n{position}", "position": position, "name": "N", "instrument": "electric",
        },
        "lessons": [
            {"slug": "l", "position": 1, "title": "L", "content_md": "x", "exercises": [exercise]}
        ],
    }  # fmt: skip
    (directory / name).write_text(json.dumps(data), encoding="utf-8")


def test_error_claro_si_una_notacion_no_valida(tmp_path):
    bad = '{"bpm": 60, "events": [{"t": 0, "dur": 0, "string": 6, "fret": 0}]}'
    _write_level(tmp_path, "malo.json", "ej-roto", 1, bad)
    with pytest.raises(CurriculumError) as error:
        read_curriculum(tmp_path)
    assert "malo.json" in str(error.value)
    assert "ej-roto" in str(error.value)


def test_error_si_se_repite_un_slug_entre_archivos(tmp_path):
    _write_level(tmp_path, "a.json", "igual", 1, '{"bpm": 60}')
    _write_level(tmp_path, "b.json", "igual", 2, '{"bpm": 60}')
    with pytest.raises(CurriculumError, match="igual"):
        read_curriculum(tmp_path)


def test_error_si_falta_la_carpeta(tmp_path):
    with pytest.raises(CurriculumError, match="no existe"):
        read_curriculum(tmp_path / "inexistente")


@pytest.mark.parametrize("exercise", all_exercises())
def test_el_ultimo_evento_cierra_en_un_compas_completo(exercise):
    notation = exercise.notation
    if not notation.events:
        return
    numerator, denominator = (int(part) for part in notation.time_signature.split("/"))
    bar_beats = numerator * 4 / denominator
    end = max(event.t + event.dur for event in notation.events)
    assert end % bar_beats == pytest.approx(0), f"{exercise.slug}: termina en el tiempo {end}"


def _write_with_tempos(directory: Path, bpm_start: int, bpm_target: int, notation_bpm: int):
    _write_level(directory, "t.json", "ej-tempo", 1, json.dumps({"bpm": notation_bpm}))
    path = directory / "t.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    exercise = data["lessons"][0]["exercises"][0]
    exercise["bpm_start"], exercise["bpm_target"] = bpm_start, bpm_target
    path.write_text(json.dumps(data), encoding="utf-8")


def test_error_claro_si_bpm_target_es_menor_que_bpm_start(tmp_path):
    _write_with_tempos(tmp_path, bpm_start=80, bpm_target=60, notation_bpm=80)
    with pytest.raises(CurriculumError) as error:
        read_curriculum(tmp_path)
    assert "t.json" in str(error.value)
    assert "ej-tempo" in str(error.value)
    assert "bpm_target" in str(error.value)


def test_error_claro_si_notation_bpm_no_es_bpm_start(tmp_path):
    _write_with_tempos(tmp_path, bpm_start=60, bpm_target=80, notation_bpm=90)
    with pytest.raises(CurriculumError) as error:
        read_curriculum(tmp_path)
    assert "t.json" in str(error.value)
    assert "ej-tempo" in str(error.value)
    assert "notation.bpm" in str(error.value)


@pytest.mark.parametrize("exercise", all_exercises())
def test_cada_ejercicio_tiene_descripcion_corta(exercise):
    assert exercise.description.strip()
    assert len(exercise.description) <= 500


def _write_with_description(directory: Path, description) -> None:
    _write_level(directory, "d.json", "ej-desc", 1, '{"bpm": 60}')
    path = directory / "d.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    exercise = data["lessons"][0]["exercises"][0]
    if description is None:
        del exercise["description"]
    else:
        exercise["description"] = description
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.parametrize("description", [None, "", "   "])
def test_error_claro_si_falta_la_descripcion_o_esta_vacia(tmp_path, description):
    _write_with_description(tmp_path, description)
    with pytest.raises(CurriculumError) as error:
        read_curriculum(tmp_path)
    assert "d.json" in str(error.value)
    assert "ej-desc" in str(error.value)
    assert "description" in str(error.value)
