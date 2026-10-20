from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from guitarra_api.infra.db.models import (
    Exercise,
    ExerciseCompletion,
    Lesson,
    Level,
    PracticeSession,
    ReminderRules,
    Settings,
)
from guitarra_api.infra.db.repositories.curriculum import CurriculumRepository


def make_lesson(session) -> Lesson:
    level = Level(position=1, name="Inicial", description="", instrument="electric")
    lesson = Lesson(level=level, position=1, title="Primeras notas", content_md="# Hola")
    session.add(lesson)
    session.flush()
    return lesson


def make_exercise(lesson: Lesson, slug: str = "escala-mi-menor", **overrides) -> Exercise:
    fields = {
        "lesson_id": lesson.id,
        "slug": slug,
        "title": "Escala de Mi menor",
        "type": "scale",
        "instrument": "electric",
        "notation": {"version": 1},
        "bpm_start": 60,
        "bpm_target": 100,
        "duration_min": 5,
        "category": "technique",
    }
    return Exercise(**{**fields, **overrides})


def test_alta_y_consulta_de_ejercicio_por_slug(session):
    lesson = make_lesson(session)
    repo = CurriculumRepository(session)
    repo.add_exercise(make_exercise(lesson))
    session.commit()

    found = repo.get_exercise_by_slug("escala-mi-menor")
    assert found is not None
    assert found.notation == {"version": 1}
    assert repo.get_exercise_by_slug("no-existe") is None
    assert [e.slug for e in repo.list_exercises(lesson.id)] == ["escala-mi-menor"]


def test_slug_de_ejercicio_es_unico(session):
    lesson = make_lesson(session)
    session.add_all([make_exercise(lesson), make_exercise(lesson)])
    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize(
    "overrides",
    [
        {"bpm_start": 0},
        {"bpm_target": -5},
        {"bpm_start": 120, "bpm_target": 100},
        {"duration_min": 0},
        {"type": "inexistente"},
        {"category": "Escalas"},
        {"instrument": "guitar"},
    ],
)
def test_ejercicio_rechaza_valores_invalidos(session, overrides):
    lesson = make_lesson(session)
    session.add(make_exercise(lesson, **overrides))
    with pytest.raises(IntegrityError):
        session.flush()


def test_ejercicio_sin_bpm_es_valido(session):
    lesson = make_lesson(session)
    session.add(make_exercise(lesson, bpm_start=None, bpm_target=None))
    session.flush()


def test_ejercicio_exige_leccion_existente(session):
    session.add(
        Exercise(
            lesson_id=999,
            slug="huerfano",
            title="x",
            type="scale",
            instrument="electric",
            notation={},
            duration_min=5,
            category="technique",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_orden_de_leccion_es_unico_dentro_del_nivel(session):
    lesson = make_lesson(session)
    session.add(Lesson(level_id=lesson.level_id, position=1, title="Otra", content_md=""))
    with pytest.raises(IntegrityError):
        session.flush()


def test_completion_se_guarda_con_timestamp_utc(session):
    lesson = make_lesson(session)
    exercise = make_exercise(lesson)
    session.add(exercise)
    session.flush()
    repo = CurriculumRepository(session)
    completion = repo.add_completion(
        ExerciseCompletion(exercise_id=exercise.id, bpm_achieved=80, instrument="electric")
    )
    session.commit()
    session.refresh(completion)
    assert completion.completed_at.utcoffset().total_seconds() == 0
    assert [c.bpm_achieved for c in repo.list_completions(exercise.id)] == [80]


def test_completion_rechaza_bpm_no_positivo(session):
    lesson = make_lesson(session)
    exercise = make_exercise(lesson)
    session.add(exercise)
    session.flush()
    session.add(ExerciseCompletion(exercise_id=exercise.id, bpm_achieved=0, instrument="electric"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_sesion_del_dia_tiene_fecha_unica(session):
    planned = [{"exercise_id": 1, "minutes": 5}]
    session.add(PracticeSession(date=date(2026, 10, 20), planned=planned, status="planned", seed=7))
    session.flush()
    session.add(PracticeSession(date=date(2026, 10, 20), planned=[], status="planned", seed=1))
    with pytest.raises(IntegrityError):
        session.flush()


def test_sesion_rechaza_estado_invalido(session):
    session.add(PracticeSession(date=date(2026, 10, 21), planned=[], status="x", seed=1))
    with pytest.raises(IntegrityError):
        session.flush()


def test_settings_tiene_defaults_y_fila_unica(session):
    session.add(Settings(id=1))
    session.flush()
    settings = session.get(Settings, 1)
    session.refresh(settings)
    assert settings.timezone == "America/Montevideo"
    assert settings.default_instrument == "electric"
    session.add(Settings(id=2))
    with pytest.raises(IntegrityError):
        session.flush()


def test_reminder_rules_defaults_y_fila_unica(session):
    session.add(ReminderRules(id=1))
    session.flush()
    rules = session.get(ReminderRules, 1)
    session.refresh(rules)
    assert rules.excluded_weekdays == []
    assert rules.inactivity_threshold_days > 0
    session.add(ReminderRules(id=2))
    with pytest.raises(IntegrityError):
        session.flush()


def test_reminder_rules_rechaza_dia_fuera_de_rango(session):
    session.add(ReminderRules(id=1, excluded_weekdays=[7]))
    with pytest.raises(IntegrityError):
        session.flush()


def test_nivel_rechaza_instrumento_invalido(session):
    session.add(Level(position=1, name="x", description="", instrument="guitar"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_completion_rechaza_instrumento_invalido(session):
    lesson = make_lesson(session)
    exercise = make_exercise(lesson)
    session.add(exercise)
    session.flush()
    session.add(ExerciseCompletion(exercise_id=exercise.id, bpm_achieved=80, instrument="bass"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_settings_rechaza_instrumento_por_defecto_invalido(session):
    session.add(Settings(id=1, default_instrument="guitar"))
    with pytest.raises(IntegrityError):
        session.flush()
