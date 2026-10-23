import json

import httpx
import pytest

from guitarra_worker.strum.catalog import load_catalog
from guitarra_worker.strum.ollama_chooser import (
    ChooserError,
    OllamaChooser,
    SongContext,
    build_prompt,
)
from guitarra_worker.strum.selection import select_pattern

CANDIDATES = [p for p in load_catalog() if p.kind == "strum" and p.beats_per_bar == 4]
CONTEXT = SongContext(title="Canción", artist="Artista", bpm=100.0, beats_per_bar=4)


def chooser_returning(body, status=200, requests=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(json.loads(request.content))
        return httpx.Response(status, json=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OllamaChooser("http://ollama.test", "qwen2.5:3b", 5.0, client=client)


def reply(content):
    return {"message": {"role": "assistant", "content": content}}


def test_valid_choice_from_catalog():
    wanted = CANDIDATES[1].id
    chooser = chooser_returning(reply(json.dumps({"pattern_id": wanted})))
    assert chooser.choose(CANDIDATES, CONTEXT).id == wanted


def test_request_is_bounded_to_candidates_with_json_schema():
    requests: list[dict] = []
    body = reply(json.dumps({"pattern_id": CANDIDATES[0].id}))
    chooser_returning(body, requests=requests).choose(CANDIDATES, CONTEXT)
    sent = requests[0]
    assert sent["model"] == "qwen2.5:3b"
    assert sent["stream"] is False
    assert sent["format"]["properties"]["pattern_id"]["enum"] == [p.id for p in CANDIDATES]
    assert all(p.id in build_prompt(CANDIDATES, CONTEXT) for p in CANDIDATES)


@pytest.mark.parametrize(
    "content",
    [
        json.dumps({"pattern_id": "inventado"}),
        json.dumps({"otro": "x"}),
        json.dumps(["a"]),
        "no es json",
        "",
    ],
)
def test_output_outside_catalog_or_malformed_is_rejected(content):
    with pytest.raises(ChooserError):
        chooser_returning(reply(content)).choose(CANDIDATES, CONTEXT)


def test_candidate_from_other_bar_is_rejected():
    other = next(p for p in load_catalog() if p.beats_per_bar == 3)
    chooser = chooser_returning(reply(json.dumps({"pattern_id": other.id})))
    with pytest.raises(ChooserError):
        chooser.choose(CANDIDATES, CONTEXT)


def test_http_error_status_is_chooser_error():
    with pytest.raises(ChooserError):
        chooser_returning({"error": "x"}, status=500).choose(CANDIDATES, CONTEXT)


def failing_chooser(error: Exception) -> OllamaChooser:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OllamaChooser("http://ollama.test", "m", 1.0, client=client)


@pytest.mark.parametrize("error", [httpx.ConnectError("rechazada"), httpx.ReadTimeout("timeout")])
def test_network_failures_are_chooser_errors(error):
    with pytest.raises(ChooserError):
        failing_chooser(error).choose(CANDIDATES, CONTEXT)


def test_selection_uses_ollama_when_valid():
    wanted = CANDIDATES[2]
    chooser = chooser_returning(reply(json.dumps({"pattern_id": wanted.id})))
    selection = select_pattern(CANDIDATES, CONTEXT, chooser)
    assert selection.pattern == wanted
    assert selection.source == "ollama"


@pytest.mark.parametrize(
    "chooser",
    [
        failing_chooser(httpx.ConnectError("rechazada")),
        failing_chooser(httpx.ReadTimeout("timeout")),
        chooser_returning(reply("basura")),
        chooser_returning(reply(json.dumps({"pattern_id": "inventado"}))),
        None,
    ],
)
def test_selection_falls_back_to_rules_without_error(chooser):
    selection = select_pattern(CANDIDATES, CONTEXT, chooser)
    assert selection.pattern in CANDIDATES
    assert selection.source == "rules"


def test_selection_without_candidates_is_none():
    assert select_pattern([], CONTEXT, None) is None
