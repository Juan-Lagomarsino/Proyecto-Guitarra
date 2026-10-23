"""Cargador del currículum contra Postgres (testcontainers): idempotencia y completions."""

import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from guitarra_api.infra.curriculum_loader import read_curriculum, sync_curriculum
from guitarra_api.infra.db.models import Exercise, ExerciseCompletion, Lesson, Level

CURRICULUM_DIR = Path(__file__).resolve().parents[2] / "curriculum"


def count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def totals(session: Session) -> tuple[int, int, int]:
    return count(session, Level), count(session, Lesson), count(session, Exercise)


def test_cargar_dos_veces_no_duplica(session: Session):
    levels = read_curriculum(CURRICULUM_DIR)

    sync_curriculum(session, levels)
    session.commit()
    first = totals(session)
    sync_curriculum(session, levels)
    session.commit()

    assert totals(session) == first
    assert first[2] >= 8


def test_actualiza_contenido_sin_borrar_completions(session: Session, tmp_path: Path):
    source = next(CURRICULUM_DIR.glob("*.json"))
    data = json.loads(source.read_text(encoding="utf-8"))
    target = tmp_path / source.name
    target.write_text(json.dumps(data), encoding="utf-8")
    sync_curriculum(session, read_curriculum(tmp_path))
    session.commit()

    exercise = session.scalars(select(Exercise).order_by(Exercise.id)).first()
    session.add(ExerciseCompletion(exercise_id=exercise.id, bpm_achieved=70, instrument="electric"))
    session.commit()
    exercise_id, slug = exercise.id, exercise.slug
    assert exercise.description == data["lessons"][0]["exercises"][0]["description"]

    data["lessons"][0]["exercises"][0]["title"] = "Título nuevo"
    data["lessons"][0]["exercises"][0]["description"] = "Descripción nueva"
    data["lessons"][0]["title"] = "Lección renombrada"
    data["level"]["name"] = "Nivel renombrado"
    target.write_text(json.dumps(data), encoding="utf-8")
    sync_curriculum(session, read_curriculum(tmp_path))
    session.commit()
    session.expire_all()

    updated = session.scalar(select(Exercise).where(Exercise.slug == slug))
    assert updated.id == exercise_id
    assert updated.title == "Título nuevo"
    assert updated.description == "Descripción nueva"
    assert updated.lesson.title == "Lección renombrada"
    assert updated.lesson.level.name == "Nivel renombrado"
    assert count(session, ExerciseCompletion) == 1


def test_insertar_una_leccion_en_el_medio_conserva_la_existente(session: Session, tmp_path: Path):
    source = next(CURRICULUM_DIR.glob("*.json"))
    data = json.loads(source.read_text(encoding="utf-8"))
    target = tmp_path / source.name
    target.write_text(json.dumps(data), encoding="utf-8")
    sync_curriculum(session, read_curriculum(tmp_path))
    session.commit()
    existing_slug = data["lessons"][1]["slug"]
    original = session.scalar(select(Lesson).where(Lesson.slug == existing_slug))
    original_id, original_content = original.id, original.content_md

    new_lesson = {
        "slug": "leccion-insertada",
        "position": 2,
        "title": "Insertada",
        "content_md": "nueva",
        "exercises": [],
    }
    data["lessons"].insert(1, new_lesson)
    for position, lesson in enumerate(data["lessons"], start=1):
        lesson["position"] = position
    target.write_text(json.dumps(data), encoding="utf-8")
    sync_curriculum(session, read_curriculum(tmp_path))
    session.commit()
    session.expire_all()

    kept = session.scalar(select(Lesson).where(Lesson.slug == existing_slug))
    assert kept.id == original_id
    assert kept.content_md == original_content
    assert kept.position == 3
    inserted = session.scalar(select(Lesson).where(Lesson.slug == "leccion-insertada"))
    assert inserted.position == 2
