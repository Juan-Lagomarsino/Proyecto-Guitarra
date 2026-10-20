from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from guitarra_api.domain.progress import compute_progress

MVD = ZoneInfo("America/Montevideo")  # UTC-3 todo el año
TODAY = date(2026, 3, 11)  # miércoles


def utc(day: int, hour: int = 15, minute: int = 0, month: int = 3) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=UTC)


def run(completions, today=TODAY, excluded=(), tz=MVD):
    return compute_progress(completions, tz, frozenset(excluded), today)


def test_sin_completions_todo_en_cero():
    result = run([])
    assert result.practiced_days == ()
    assert result.completions_per_day == {}
    assert (result.current_streak, result.max_streak, result.total_days) == (0, 0, 0)


def test_completion_a_las_2359_locales_cae_en_ese_dia():
    # 23:59 en Montevideo = 02:59 UTC del día siguiente
    result = run([utc(11, 2, 59)])
    assert result.practiced_days == (date(2026, 3, 10),)


def test_completion_a_las_0001_locales_cae_en_el_dia_nuevo():
    # 00:01 en Montevideo = 03:01 UTC
    result = run([utc(11, 3, 1)])
    assert result.practiced_days == (date(2026, 3, 11),)


def test_completion_a_las_0230_utc_sigue_siendo_ayer_en_montevideo():
    result = run([utc(11, 2, 30)])
    assert result.practiced_days == (date(2026, 3, 10),)


def test_misma_completion_con_dos_zonas_cae_en_dias_distintos():
    moment = [utc(11, 2, 30)]
    montevideo = run(moment, tz=MVD)
    tokio = run(moment, tz=ZoneInfo("Asia/Tokyo"))
    assert montevideo.practiced_days == (date(2026, 3, 10),)
    assert tokio.practiced_days == (date(2026, 3, 11),)


def test_acepta_nombre_iana_como_zona():
    result = compute_progress([utc(11, 2, 30)], "America/Montevideo", frozenset(), TODAY)
    assert result.practiced_days == (date(2026, 3, 10),)


def test_varias_completions_el_mismo_dia_cuentan_un_dia_y_se_acumulan():
    result = run([utc(11, 13), utc(11, 14), utc(11, 20)])
    assert result.total_days == 1
    assert result.completions_per_day == {date(2026, 3, 11): 3}
    assert result.current_streak == 1


def test_racha_de_dias_consecutivos_hasta_hoy():
    result = run([utc(9), utc(10), utc(11)])
    assert (result.current_streak, result.max_streak, result.total_days) == (3, 3, 3)


def test_dia_excluido_sin_practica_en_medio_no_corta_ni_suma():
    # lunes 9 y miércoles 11 practicados, martes 10 excluido
    result = run([utc(9), utc(11)], excluded={1})
    assert result.current_streak == 2
    assert result.max_streak == 2
    assert result.total_days == 2


def test_dia_no_excluido_sin_practica_en_medio_corta_la_racha():
    result = run([utc(9), utc(11)])
    assert result.current_streak == 1
    assert result.max_streak == 1


def test_practica_en_dia_excluido_suma():
    result = run([utc(9), utc(10), utc(11)], excluded={1})
    assert result.current_streak == 3
    assert result.total_days == 3


def test_hoy_sin_practicar_con_ayer_practicado_mantiene_la_racha():
    result = run([utc(9), utc(10)])
    assert result.current_streak == 2


def test_hoy_sin_practicar_y_antes_de_ayer_sin_practicar_la_racha_es_cero():
    result = run([utc(8)])
    assert result.current_streak == 0
    assert result.max_streak == 1


def test_hoy_excluido_sin_practicar_no_corta_la_racha():
    # hoy miércoles excluido; lunes y martes practicados
    result = run([utc(9), utc(10)], excluded={2})
    assert result.current_streak == 2


def test_hoy_y_ayer_excluidos_sin_practicar_buscan_el_ultimo_dia_no_excluido():
    # martes y miércoles excluidos; lunes practicado
    result = run([utc(9)], excluded={1, 2})
    assert result.current_streak == 1


def test_hoy_sin_practicar_y_ayer_excluido_mantiene_la_racha_previa():
    result = run([utc(9)], excluded={1})
    assert result.current_streak == 1


def test_racha_maxima_pasada_mayor_que_la_actual():
    result = run([utc(1), utc(2), utc(3), utc(4), utc(5), utc(10), utc(11)])
    assert result.current_streak == 2
    assert result.max_streak == 5
    assert result.total_days == 7


def test_racha_maxima_atraviesa_dias_excluidos_del_pasado():
    # 2 (lun) practicado, 3 (mar) excluido, 4 (mié) practicado
    result = run([utc(2), utc(4)], excluded={1})
    assert result.max_streak == 2


def test_todos_los_dias_excluidos_sin_practica_da_racha_cero():
    result = run([], excluded=range(7))
    assert result.current_streak == 0


def test_practicas_desordenadas_dan_el_mismo_resultado():
    ordered = run([utc(9), utc(10), utc(11)])
    shuffled = run([utc(11), utc(9), utc(10)])
    assert ordered == shuffled


def test_practiced_days_viene_ordenado():
    result = run([utc(11), utc(9)])
    assert result.practiced_days == (date(2026, 3, 9), date(2026, 3, 11))


def test_datetime_naive_levanta_value_error():
    with pytest.raises(ValueError, match="zona"):
        run([datetime(2026, 3, 11, 15, 0)])


def test_dia_excluido_fuera_de_rango_levanta_value_error():
    with pytest.raises(ValueError, match="0 y 6"):
        run([], excluded={7})


def test_resultado_es_inmutable():
    result = run([])
    with pytest.raises(AttributeError):
        result.current_streak = 5  # type: ignore[misc]
