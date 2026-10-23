"""Spotify Web API con client credentials: solo metadatos de un tema (no entrega audio)."""

import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from guitarra_worker.pipeline.step import PermanentStepError, RetryableStepError

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_URL = "https://api.spotify.com/v1"
MISSING_CREDENTIALS = (
    "Faltan SPOTIFY_CLIENT_ID/SECRET en el .env; por ahora pegá el link de YouTube "
    "o buscá por nombre"
)
TOKEN_MARGIN_S = 30.0  # se renueva un poco antes de que venza


@dataclass(frozen=True)
class TrackInfo:
    title: str
    artist: str
    duration_s: float
    year: int | None


class SpotifyAdapter:
    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._clock = clock
        self._http = httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0), transport=transport)
        self._token: str | None = None
        self._token_expires_at = 0.0

    @property
    def configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def track(self, spotify_id: str) -> TrackInfo:
        if not self.configured:
            raise PermanentStepError(MISSING_CREDENTIALS)
        data = self._get_json(f"{API_URL}/tracks/{spotify_id}")
        return TrackInfo(
            title=data["name"],
            artist=", ".join(artist["name"] for artist in data.get("artists", [])),
            duration_s=data["duration_ms"] / 1000,
            year=_release_year(data.get("album", {}).get("release_date")),
        )

    def _get_json(self, url: str) -> dict:
        response = self._send("GET", url, headers={"Authorization": f"Bearer {self._get_token()}"})
        if response.status_code == 401:  # token revocado antes de vencer: se pide otro una vez
            self._token = None
            response = self._send(
                "GET", url, headers={"Authorization": f"Bearer {self._get_token()}"}
            )
        _raise_for_status(response, "tema")
        return response.json()

    def _get_token(self) -> str:
        if self._token and self._clock() < self._token_expires_at:
            return self._token
        response = self._send(
            "POST",
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(self._client_id, self._client_secret),
        )
        if response.status_code in (400, 401):
            raise PermanentStepError(
                "Spotify rechazó SPOTIFY_CLIENT_ID/SECRET: revisalos en el .env"
            )
        _raise_for_status(response, "token")
        body = response.json()
        self._token = body["access_token"]
        self._token_expires_at = self._clock() + float(body["expires_in"]) - TOKEN_MARGIN_S
        return self._token

    def _send(self, method: str, url: str, **kwargs) -> httpx.Response:
        try:
            return self._http.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise RetryableStepError(f"Spotify: error de red ({exc})") from exc


def _release_year(release_date: str | None) -> int | None:
    return int(release_date[:4]) if release_date and release_date[:4].isdigit() else None


def _raise_for_status(response: httpx.Response, what: str) -> None:
    status = response.status_code
    if status < 400:
        return
    if status == 429 or status >= 500:
        raise RetryableStepError(f"Spotify: {what} no disponible por ahora (HTTP {status})")
    if status == 404:
        raise PermanentStepError("Spotify: no existe ese tema")
    raise PermanentStepError(f"Spotify: HTTP {status} al pedir {what}")
