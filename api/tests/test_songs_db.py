"""Modelos de canciones y restricciones de la base (Postgres de testcontainers)."""

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from conftest import alembic_config
from guitarra_api.domain.song_chart import SongChartContent
from guitarra_api.infra.db.models import (
    AnalysisJob,
    AudioAsset,
    Correction,
    Exercise,
    Song,
    SongChart,
    SongSection,
)
from guitarra_api.infra.db.repositories.songs import SongRepository
from test_db_models import make_exercise, make_lesson

SONG_TABLES = {
    "songs",
    "song_sections",
    "song_charts",
    "audio_assets",
    "analysis_jobs",
    "corrections",
}


def chart_content(instrument: str = "electric", **overrides) -> SongChartContent:
    data = {
        "instrument": instrument,
        "bpm": 100,
        "sections": [
            {
                "id": "intro",
                "name": "Intro",
                "start_s": 0,
                "end_s": 10,
                "order": 0,
                "chord_source": "detected",
                "chords": [
                    {
                        "t_s": 1,
                        "name": "Am",
                        "shape": ["x", 0, 2, 2, 1, 0],
                        "confidence": 0.8,
                    }
                ],
            }
        ],
    }
    return SongChartContent.model_validate({**data, **overrides})


@pytest.fixture
def repo(session) -> SongRepository:
    return SongRepository(session)


@pytest.fixture
def song(repo) -> Song:
    return repo.add_song(
        title="Flaca", artist="Andrés Calamaro", source="youtube", youtube_id="abc123"
    )


def make_section(session, song: Song) -> SongSection:
    section = SongSection(
        song_id=song.id, slug="intro", name="Intro", start_s=0, end_s=10, position=0
    )
    session.add(section)
    session.flush()
    return section


# --- migración ---------------------------------------------------------------------------


def test_0003_ida_y_vuelta_desde_0002(database_url):
    config = alembic_config()
    engine = create_engine(database_url)
    try:
        command.upgrade(config, "head")
        assert SONG_TABLES <= set(inspect(engine).get_table_names())
        command.downgrade(config, "0002")
        assert not SONG_TABLES & set(inspect(engine).get_table_names())
        columns = {c["name"]: c for c in inspect(engine).get_columns("exercises")}
        assert "song_section_id" not in columns
        assert columns["lesson_id"]["nullable"] is False
        command.upgrade(config, "head")
        columns = {c["name"]: c for c in inspect(engine).get_columns("exercises")}
        assert columns["lesson_id"]["nullable"] is True
        assert columns["song_section_id"]["nullable"] is True
    finally:
        engine.dispose()


def test_la_migracion_conserva_los_ejercicios_existentes(database_url):
    config = alembic_config()
    engine = create_engine(database_url)
    try:
        command.downgrade(config, "0002")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO levels (slug, position, name, description, instrument) "
                    "VALUES ('n', 1, 'N', '', 'electric')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO lessons (level_id, slug, position, title, content_md) "
                    "SELECT id, 'l', 1, 'L', '' FROM levels"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO exercises (lesson_id, slug, title, type, instrument, notation, "
                    "duration_min, category) SELECT id, 'e', 'E', 'scale', 'electric', '{}', 5, "
                    "'technique' FROM lessons"
                )
            )
        command.upgrade(config, "head")
        with engine.connect() as connection:
            row = connection.execute(text("SELECT lesson_id, song_section_id FROM exercises")).one()
        assert row.lesson_id is not None and row.song_section_id is None
    finally:
        with engine.begin() as connection:
            connection.execute(text("TRUNCATE exercises, lessons, levels RESTART IDENTITY CASCADE"))
        engine.dispose()


# --- restricciones -----------------------------------------------------------------------


def test_youtube_id_es_unico(repo):
    repo.add_song(title="A", artist="B", source="youtube", youtube_id="dup")
    with pytest.raises(IntegrityError):
        repo.add_song(title="C", artist="D", source="youtube", youtube_id="dup")


def test_varias_canciones_sin_youtube_id_conviven(repo):
    repo.add_song(title="A", artist="B", source="search")
    repo.add_song(title="C", artist="D", source="search")


def test_spotify_id_es_unico(repo):
    repo.add_song(title="A", artist="B", source="spotify", spotify_id="sp1")
    with pytest.raises(IntegrityError):
        repo.add_song(title="C", artist="D", source="spotify", spotify_id="sp1")


def test_fuente_y_estado_invalidos_se_rechazan(session):
    session.add(Song(title="A", artist="B", source="radio"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_estado_de_analisis_invalido_se_rechaza(session):
    session.add(Song(title="A", artist="B", source="search", analysis_status="meh"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_la_cancion_nueva_queda_en_cola(song):
    assert song.analysis_status == "queued"


def test_seccion_con_inicio_mayor_que_fin_se_rechaza(session, song):
    session.add(SongSection(song_id=song.id, slug="x", name="X", start_s=5, end_s=5, position=0))
    with pytest.raises(IntegrityError):
        session.flush()


def test_la_version_del_chart_es_unica_por_cancion_e_instrumento(session, song):
    content = chart_content().model_dump(mode="json")
    session.add(
        SongChart(song_id=song.id, instrument="electric", version=1, origin="auto", content=content)
    )
    session.flush()
    session.add(
        SongChart(song_id=song.id, instrument="electric", version=1, origin="user", content=content)
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_el_chart_acepta_la_misma_version_en_otro_instrumento(session, song):
    for instrument in ("electric", "classical"):
        content = chart_content(instrument).model_dump(mode="json")
        session.add(
            SongChart(
                song_id=song.id, instrument=instrument, version=1, origin="auto", content=content
            )
        )
    session.flush()


def test_el_chart_rechaza_contenido_invalido_al_guardar(song):
    with pytest.raises(ValueError):
        SongChart(
            song_id=song.id, instrument="electric", version=1, origin="auto", content={"bpm": 0}
        )


def test_el_chart_rechaza_origen_y_confianza_invalidos(session, song):
    content = chart_content().model_dump(mode="json")
    session.add(
        SongChart(song_id=song.id, instrument="electric", version=1, origin="otro", content=content)
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_ejercicio_de_leccion_se_guarda_y_sigue_cargando(session):
    exercise = make_exercise(make_lesson(session))
    session.add(exercise)
    session.flush()
    assert session.get(Exercise, exercise.id).lesson is not None


def test_ejercicio_de_cancion_se_guarda(session, song):
    section = make_section(session, song)
    exercise = make_exercise(make_lesson(session))
    exercise.lesson_id = None
    exercise.song_section_id = section.id
    session.add(exercise)
    session.flush()


def test_ejercicio_con_leccion_y_seccion_a_la_vez_se_rechaza(session, song):
    section = make_section(session, song)
    exercise = make_exercise(make_lesson(session))
    exercise.song_section_id = section.id
    session.add(exercise)
    with pytest.raises(IntegrityError):
        session.flush()


def test_ejercicio_sin_leccion_ni_seccion_se_rechaza(session):
    exercise = make_exercise(make_lesson(session))
    exercise.lesson_id = None
    session.add(exercise)
    with pytest.raises(IntegrityError):
        session.flush()


def test_borrar_la_cancion_borra_secciones_charts_jobs_y_correcciones(session, song):
    make_section(session, song)
    chart = SongRepository(session).add_chart(song.id, "auto", chart_content())
    session.add_all(
        [
            AnalysisJob(song_id=song.id),
            AudioAsset(song_id=song.id, kind="original", path="a.wav", format="wav"),
            Correction(song_chart_id=chart.id, diff={"op": "replace"}),
        ]
    )
    session.commit()
    session.execute(text("DELETE FROM songs"))
    for table in SONG_TABLES - {"songs"}:
        assert session.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0


def test_la_cola_arranca_con_valores_por_defecto(session, song):
    job = AnalysisJob(song_id=song.id)
    session.add(job)
    session.commit()
    assert (job.status, job.attempts, job.max_attempts) == ("queued", 0, 3)
    assert job.claimed_by is None and job.lease_until is None and job.current_step is None


def test_estado_de_trabajo_invalido_se_rechaza(session, song):
    session.add(AnalysisJob(song_id=song.id, status="colgado"))
    with pytest.raises(IntegrityError):
        session.flush()


# --- repositorio -------------------------------------------------------------------------


def test_add_chart_asigna_versiones_crecientes_por_instrumento(repo, song):
    first = repo.add_chart(song.id, "auto", chart_content("electric"))
    second = repo.add_chart(song.id, "auto", chart_content("electric"))
    classical = repo.add_chart(song.id, "auto", chart_content("classical"))
    assert (first.version, second.version, classical.version) == (1, 2, 1)


def test_add_chart_guarda_la_confianza_global(repo, song):
    chart = repo.add_chart(song.id, "auto", chart_content())
    assert chart.confidence == pytest.approx(0.8)


def test_chart_vigente_es_none_sin_charts(repo, song):
    assert repo.current_chart(song.id, "electric") is None


def test_chart_vigente_es_el_ultimo_auto_si_no_hay_de_usuario(repo, song):
    repo.add_chart(song.id, "auto", chart_content())
    latest = repo.add_chart(song.id, "auto", chart_content())
    assert repo.current_chart(song.id, "electric").id == latest.id


def test_chart_vigente_prefiere_el_de_usuario_aunque_haya_un_auto_mas_nuevo(repo, song):
    repo.add_chart(song.id, "auto", chart_content())
    user = repo.add_chart(song.id, "user", chart_content())
    repo.add_chart(song.id, "auto", chart_content())  # reanálisis posterior
    assert repo.current_chart(song.id, "electric").id == user.id


def test_chart_vigente_toma_el_ultimo_de_usuario(repo, song):
    repo.add_chart(song.id, "user", chart_content())
    latest = repo.add_chart(song.id, "user", chart_content())
    assert repo.current_chart(song.id, "electric").id == latest.id


def test_chart_vigente_no_mezcla_instrumentos_ni_canciones(repo, song):
    other = repo.add_song(title="X", artist="Y", source="search")
    repo.add_chart(other.id, "user", chart_content("classical"))
    assert repo.current_chart(song.id, "classical") is None


def test_consultas_de_cancion(repo, song):
    assert repo.get(song.id).title == "Flaca"
    assert repo.get_by_youtube_id("abc123").id == song.id
    assert repo.get_by_youtube_id("nope") is None
    assert repo.get_by_spotify_id("nope") is None
    assert [s.id for s in repo.list_songs()] == [song.id]


def test_la_cola_tiene_indice_de_estado_y_lease_y_columnas_de_cierre(migrated_engine):
    inspector = inspect(migrated_engine)
    indexes = {i["name"]: i["column_names"] for i in inspector.get_indexes("analysis_jobs")}
    assert indexes["ix_analysis_jobs_status_lease_until"] == ["status", "lease_until"]
    columns = {c["name"]: c for c in inspector.get_columns("analysis_jobs")}
    assert columns["finished_at"]["nullable"] is True
    assert columns["updated_at"]["nullable"] is False
