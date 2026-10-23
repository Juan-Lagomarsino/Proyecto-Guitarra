import json

import httpx
import pytest

from guitarra_worker.api_client import ApiClient, Job

JOB = {
    "job_id": 7,
    "song_id": 3,
    "title": "T",
    "artist": "A",
    "source": "youtube",
    "url": "u",
    "youtube_id": "abc123",
    "spotify_id": None,
    "attempt": 1,
}


class FakeApi:
    """API falsa sobre httpx.MockTransport. Registra las llamadas."""

    def __init__(self, jobs=None, heartbeat_status=200):
        self.jobs = list(jobs or [])
        self.heartbeat_status = heartbeat_status
        self.calls = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        self.calls.append((request.url.path, body, request.headers.get("authorization")))
        path = request.url.path
        if path.endswith("/claim"):
            return httpx.Response(200, json=self.jobs.pop(0)) if self.jobs else httpx.Response(204)
        if path.endswith("/heartbeat"):
            return httpx.Response(self.heartbeat_status)
        return httpx.Response(200)

    def paths(self, suffix):
        return [c for c in self.calls if c[0].endswith(suffix)]


@pytest.fixture
def job():
    return Job.model_validate(JOB)


@pytest.fixture
def make_client():
    def _make(api: FakeApi, **kwargs):
        kwargs.setdefault("sleep", lambda s: None)
        return ApiClient(
            "http://api", "tok", "w1", transport=httpx.MockTransport(api.handler), **kwargs
        )

    return _make
