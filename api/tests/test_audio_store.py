import pytest

from guitarra_api.infra.audio_store import AudioStore, AudioTooLargeError


def test_guarda_con_nombre_por_cancion_y_tipo(tmp_path):
    store = AudioStore(tmp_path)
    stored = store.save(7, "stem", "m4a", iter([b"ab", b"cd"]), max_bytes=10)
    assert stored.relative_path == "7/stem.m4a"
    assert stored.size == 4
    assert store.resolve("7/stem.m4a").read_bytes() == b"abcd"


def test_si_se_pasa_del_tope_borra_el_temporal(tmp_path):
    store = AudioStore(tmp_path)
    with pytest.raises(AudioTooLargeError):
        store.save(7, "stem", "m4a", iter([b"abc", b"def"]), max_bytes=5)
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


def test_resolve_rechaza_salirse_de_la_carpeta(tmp_path):
    with pytest.raises(ValueError):
        AudioStore(tmp_path).resolve("../afuera.m4a")


def test_remove_ignora_lo_inexistente(tmp_path):
    AudioStore(tmp_path).remove("1/original.m4a")


def test_los_tipos_de_la_api_coinciden_con_los_del_modelo():
    from typing import get_args

    from guitarra_api.http.audio_schemas import AudioKind
    from guitarra_api.infra.db.models import AUDIO_ASSET_KINDS

    assert get_args(AudioKind) == AUDIO_ASSET_KINDS
