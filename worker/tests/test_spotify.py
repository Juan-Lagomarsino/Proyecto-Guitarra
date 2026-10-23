import httpx
import pytest

from guitarra_worker.adapters.spotify import MISSING_CREDENTIALS, SpotifyAdapter, TrackInfo
from guitarra_worker.pipeline.step import PermanentStepError, RetryableStepError

TRACK = {
    "name": "Wonderwall",
    "artists": [{"name": "Oasis"}, {"name": "Invitado"}],
    "duration_ms": 258_773,
    "album": {"release_date": "1995-10-30"},
}


class FakeSpotify:
    def __init__(self, track_status=200, token_status=200, expires_in=3600):
        self.track_status = track_status
        self.token_status = token_status
        self.expires_in = expires_in
        self.token_calls = 0
        self.track_calls = 0
        self.last_auth = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "accounts.spotify.com":
            self.token_calls += 1
            if self.token_status != 200:
                return httpx.Response(self.token_status, json={"error": "invalid_client"})
            token = {"access_token": f"tok{self.token_calls}", "expires_in": self.expires_in}
            return httpx.Response(200, json=token)
        self.track_calls += 1
        self.last_auth = request.headers["authorization"]
        if self.track_status != 200:
            return httpx.Response(self.track_status)
        return httpx.Response(200, json=TRACK)


def adapter(fake, clock=None):
    kwargs = {"clock": clock} if clock else {}
    return SpotifyAdapter("id", "secret", transport=httpx.MockTransport(fake.handler), **kwargs)


def test_track_devuelve_titulo_artistas_duracion_y_anio():
    fake = FakeSpotify()
    info = adapter(fake).track("4iV5W9uYEdYUVa79Axb7Rh")
    assert info == TrackInfo("Wonderwall", "Oasis, Invitado", pytest.approx(258.773), 1995)
    assert fake.last_auth == "Bearer tok1"


def test_sin_credenciales_falla_claro_sin_red():
    fake = FakeSpotify()
    spotify = SpotifyAdapter("", "", transport=httpx.MockTransport(fake.handler))
    with pytest.raises(PermanentStepError) as error:
        spotify.track("x")
    assert str(error.value) == MISSING_CREDENTIALS
    assert fake.token_calls == 0


def test_cachea_el_token_hasta_que_vence():
    fake = FakeSpotify(expires_in=100)
    now = [0.0]
    spotify = adapter(fake, clock=lambda: now[0])
    spotify.track("a")
    now[0] = 50
    spotify.track("a")
    assert fake.token_calls == 1
    now[0] = 80  # ya dentro del margen de renovación
    spotify.track("a")
    assert fake.token_calls == 2


def test_credenciales_rechazadas_no_se_reintenta():
    with pytest.raises(PermanentStepError, match="rechazó"):
        adapter(FakeSpotify(token_status=401)).track("x")


def test_tema_inexistente_no_se_reintenta():
    with pytest.raises(PermanentStepError, match="no existe"):
        adapter(FakeSpotify(track_status=404)).track("x")


@pytest.mark.parametrize("status", [429, 500, 503])
def test_limite_y_errores_del_servidor_son_reintentables(status):
    with pytest.raises(RetryableStepError):
        adapter(FakeSpotify(track_status=status)).track("x")


def test_error_de_red_es_reintentable():
    def boom(request):
        raise httpx.ConnectError("sin red")

    spotify = SpotifyAdapter("id", "secret", transport=httpx.MockTransport(boom))
    with pytest.raises(RetryableStepError):
        spotify.track("x")


def test_token_revocado_pide_otro_una_vez():
    class Revoked(FakeSpotify):
        def handler(self, request):
            response = super().handler(request)
            if request.url.host != "accounts.spotify.com" and self.track_calls == 1:
                return httpx.Response(401)
            return response

    fake = Revoked()
    assert adapter(fake).track("x").title == "Wonderwall"
    assert fake.token_calls == 2
