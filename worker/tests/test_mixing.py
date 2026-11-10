import numpy as np
import pytest

from guitarra_worker.domain.mixing import PEAK_LIMIT, mix_without_guitar

RATE = 8000


def tone(freq, amp, n=RATE):
    t = np.arange(n) / RATE
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)[:, None].repeat(2, axis=1)


def stems(amp=0.1):
    names = ["drums", "bass", "other", "vocals", "guitar", "piano"]
    return {name: tone(100 * (i + 1), amp) for i, name in enumerate(names)}


def test_resta_solo_la_guitarra():
    s = stems()
    expected = sum(v for k, v in s.items() if k != "guitar")
    assert np.allclose(mix_without_guitar(s), expected, atol=1e-6)


def test_no_depende_de_la_guitarra():
    a, b = stems(), stems()
    b["guitar"] = b["guitar"] * 50
    assert np.array_equal(mix_without_guitar(a), mix_without_guitar(b))


def test_no_satura_y_conserva_el_balance():
    s = stems(amp=0.9)
    mixed = mix_without_guitar(s)
    raw = sum(v for k, v in s.items() if k != "guitar")
    assert np.abs(raw).max() > 1
    assert np.abs(mixed).max() <= PEAK_LIMIT + 1e-6
    gain = mixed / np.where(raw == 0, 1, raw)
    nonzero = np.abs(raw) > 1e-3
    assert np.allclose(gain[nonzero], gain[nonzero][0], atol=1e-4)  # una sola ganancia global


def test_limite_es_menos_1_dbfs():
    assert PEAK_LIMIT == pytest.approx(10 ** (-1 / 20))


def test_no_sube_el_volumen_si_ya_entra():
    s = stems(amp=0.05)
    raw = sum(v for k, v in s.items() if k != "guitar")
    assert np.allclose(mix_without_guitar(s), raw, atol=1e-6)


def test_largos_distintos_se_recortan_al_menor():
    s = stems()
    s["bass"] = s["bass"][:-100]
    assert len(mix_without_guitar(s)) == RATE - 100


def test_falta_la_guitarra_o_otra_pista():
    s = stems()
    del s["piano"]
    with pytest.raises(ValueError, match="piano"):
        mix_without_guitar(s)


def test_silencio_no_da_nan():
    s = {k: np.zeros((10, 2), dtype=np.float32) for k in stems()}
    assert not np.isnan(mix_without_guitar(s)).any()
