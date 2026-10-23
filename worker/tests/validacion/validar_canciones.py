"""Validación del análisis con las 5 canciones de Juan Pedro (F2-T19). No va en la suite de CI.

Corre el pipeline real del worker (beat_this, librosa, BTC, Krumhansl, armado) sobre el audio en
caché y mide, por canción: BPM contra la referencia, % de secciones del chart cuyos acordes
coinciden con Cifra Club (ver `metrica.py`) en dos modos (a: sin cifra; b: con la cifra cargada como
texto, ADR 0012) y tiempo de proceso. Salida: tablas en Markdown por stdout y JSON con `--json`.

    cd worker
    .\\.venv\\Scripts\\python tests\\validacion\\validar_canciones.py --json salida.json

El audio sale de `--audio-dir` (por defecto `<GUITAR_CACHE_DIR>/spike`, los WAV del spike T01).
Los pasos intermedios se cachean en `--cache-dir` (por defecto `<GUITAR_CACHE_DIR>/validacion`);
borrarlo da los tiempos en frío. En el modo b los pasos de audio salen de la caché del modo a.
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from metrica import (  # noqa: E402
    ciclo_minimo,
    cobertura,
    cobertura_vocabulario,
    coincide_vocabulario,
    flujo,
    mejor_referencia,
)

from guitarra_worker.adapters.ffmpeg import read_wav_info  # noqa: E402
from guitarra_worker.api_client import Job  # noqa: E402
from guitarra_worker.config import Settings  # noqa: E402
from guitarra_worker.domain.alignment import align  # noqa: E402
from guitarra_worker.domain.chart_assembly import merge_detected  # noqa: E402
from guitarra_worker.pipeline.registry import assemble_result, default_steps  # noqa: E402
from guitarra_worker.pipeline.runner import Heartbeat, run_pipeline  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cifraclub"


@dataclass(frozen=True)
class Song:
    slug: str
    title: str
    artist: str
    youtube_id: str
    bpm_ref: float  # songbpm.com (spikes/analisis/songs.py)


SONGS = [
    Song("flaca", "Flaca", "Andrés Calamaro", "UCF9oHXhDMU", 109),
    Song("de-musica-ligera", "De música ligera", "Soda Stereo", "T_FkEw27XJ0", 124),
    Song("boys-dont-cry", "Boys Don't Cry", "The Cure", "9GkVhgIeGJQ", 169),
    Song("cerca-del-fuego", "Cerca del fuego", "La Barranca", "-HlcQsAsJbg", 115),
    Song("no-voy-en-tren", "No voy en tren", "Charly García", "P3L10KNMptw", 124),
]


class CannedStep:
    """Reemplaza `source` y `download`: el audio ya está en disco."""

    version = "1"

    def __init__(self, name: str, output: dict[str, Any]) -> None:
        self.name, self._output = name, output

    def run(self, ctx: Any) -> dict[str, Any]:
        return self._output


class TimedStep:
    """Mide el tiempo de `run`. Delega el resto (name, version, cache_token)."""

    def __init__(self, inner: Any, timings: dict[str, float]) -> None:
        self._inner, self._timings = inner, timings

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._inner, attr)

    def run(self, ctx: Any) -> dict[str, Any]:
        start = time.perf_counter()
        output = self._inner.run(ctx)
        self._timings[self._inner.name] = time.perf_counter() - start
        return output


def render_cifra(fixture: dict[str, Any]) -> str | None:
    """Texto plano estilo Cifra Club a partir de la fixture (encabezado [Sección] + acordes)."""
    sections = fixture.get("sections") or []
    if not sections or fixture.get("disponible") is False:
        return None
    lines = [f"{fixture['artist']} - {fixture['title']}"]
    if fixture.get("tonalidad"):
        lines.append(f"Tom: {fixture['tonalidad']}")
    if fixture.get("capo"):
        lines.append(f"Capotraste na {fixture['capo']}ª casa")
    for section in sections:
        header = f"[{section['name']}]" if section["name"] else None
        lines += ["", *([header] if header else []), "  ".join(section["chords"])]
    return "\n".join(lines) + "\n"


def run_mode(
    song: Song, steps: list[Any], cifra_text: str | None, cache_dir: Path
) -> tuple[dict[str, Any], dict[str, float], float]:
    timings: dict[str, float] = {}
    job = Job(
        job_id=1,
        song_id=1,
        title=song.title,
        artist=song.artist,
        source="youtube",
        youtube_id=song.youtube_id,
        cifra_text=cifra_text,
    )
    timed = [TimedStep(step, timings) for step in steps]
    start = time.perf_counter()
    with Heartbeat(lambda step: None, 60) as heartbeat:
        result = run_pipeline(timed, job, cache_dir, heartbeat, assemble_result)
    return result, timings, time.perf_counter() - start


def evaluate_sections(
    result: dict[str, Any], fixture: dict[str, Any], capo: int
) -> dict[str, Any] | None:
    """Métricas de coincidencia contra la referencia; None si no hay referencia utilizable.

    Cifra con varias secciones: método "ciclo" (ver `metrica.py`). Si la sección del chart se llama
    como una de la referencia (modo b), se compara solo con las de ese nombre. Cifra plana (una
    sola sección): método "vocabulario".
    """
    if not fixture.get("sections"):
        return None
    flat = len(fixture["sections"]) == 1
    reference = [(s["name"], ciclo_minimo(flujo(s["chords"], capo))) for s in fixture["sections"]]
    vocabulary = flujo(fixture["sections"][0]["chords"], capo) if flat else []
    chart = next(c for c in result["charts"] if c["instrument"] == "electric")
    verdicts = []
    for section in chart["sections"]:
        stream = flujo([chord["name"] for chord in section["chords"]])
        same_name = [r for r in reference if r[0] == section["name"]]
        verdict = (
            coincide_vocabulario(stream, vocabulary)
            if flat
            else mejor_referencia(stream, same_name or reference)
        )
        verdicts.append(
            {
                "seccion": section["name"],
                "acordes": len(stream),
                "fuente": section["chord_source"],
                "coincide": verdict.coincide,
                "puntaje": round(verdict.puntaje, 2),
                "pureza": round(verdict.pureza, 2),
                "referencia": verdict.referencia,
            }
        )
    song_stream = flujo([c["name"] for s in chart["sections"] for c in s["chords"]])
    if flat:
        covered_pct = round(100 * cobertura_vocabulario(song_stream, vocabulary), 1)
        covered, total_ref = None, None
    else:
        flags = [cobertura(song_stream, cycle) for _, cycle in reference]
        covered, total_ref = sum(flags), len(reference)
        covered_pct = round(100 * covered / total_ref, 1)
    hits = sum(v["coincide"] for v in verdicts)
    return {
        "metodo": "vocabulario" if flat else "ciclo",
        "secciones_chart": len(verdicts),
        "coinciden": hits,
        "pct_chart": round(100 * hits / len(verdicts), 1) if verdicts else 0.0,
        "secciones_ref": total_ref,
        "cubiertas": covered,
        "pct_ref": covered_pct,
        "detalle": verdicts,
    }


def alignment_similarity(outputs: dict[str, Any]) -> float | None:
    cifra = outputs.get("cifraclub")
    if not cifra or not cifra.get("found"):
        return None
    detected = merge_detected(outputs["chords"]["chords"])
    names = [c for s in cifra["sections"] for c in s["chords"]]
    return round(align(names, [d.label for d in detected]).similarity, 3)


def summarize(
    song: Song,
    result: dict[str, Any],
    timings: dict[str, float],
    total: float,
    fixture: dict[str, Any],
    outputs: dict[str, Any],
) -> dict[str, Any]:
    bpm = result["metadata"].get("bpm")
    chart = next(c for c in result["charts"] if c["instrument"] == "classical")
    return {
        "bpm": round(bpm, 1) if bpm else None,
        "bpm_error_pct": round(100 * (bpm - song.bpm_ref) / song.bpm_ref, 1) if bpm else None,
        "tonalidad": result["metadata"].get("key"),
        "secciones": len(chart["sections"]),
        "acordes": sum(len(s["chords"]) for s in chart["sections"]),
        "fuentes": [s["chord_source"] for s in chart["sections"]],
        "capo_clasica": chart.get("capo"),
        "similitud_cifra": alignment_similarity(outputs),
        "tiempo_s": round(total, 1),
        "tiempos_pasos_s": {k: round(v, 1) for k, v in timings.items()},
        "coincidencia": evaluate_sections(result, fixture, int(fixture.get("capo") or 0)),
    }


def read_outputs(cache_dir: Path, song: Song) -> dict[str, Any]:
    steps_dir = cache_dir / song.youtube_id / "steps"
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))["output"]
        for path in steps_dir.glob("*.json")
    }


def validate_song(
    song: Song, steps: list[Any], cache_dir: Path, cifra_file: Path | None = None
) -> dict[str, Any]:
    fixture = json.loads((FIXTURES / f"{song.slug}.json").read_text(encoding="utf-8"))
    cifra = cifra_file.read_text(encoding="utf-8") if cifra_file else render_cifra(fixture)
    report: dict[str, Any] = {"cifra_chars": len(cifra) if cifra else None, "b": None}
    for mode, text in (("a", None), ("b", cifra)):
        if mode == "b" and text is None:
            continue
        result, timings, total = run_mode(song, steps, text, cache_dir)
        outputs = read_outputs(cache_dir, song)
        report[mode] = summarize(song, result, timings, total, fixture, outputs)
    return report


def build_steps(song: Song, audio_dir: Path) -> list[Any]:
    wav = audio_dir / f"{song.slug}.wav"
    info = read_wav_info(wav)
    duration = round(info.duration_s, 3)
    source = {
        "youtube_id": song.youtube_id,
        "title": song.title,
        "artist": song.artist,
        "duration_s": duration,
        "year": None,
        "resolved_from": "youtube",
    }
    download = {
        "wav_path": str(wav.resolve()),
        "sample_rate": info.sample_rate,
        "channels": info.channels,
        "duration_s": duration,
    }
    real = default_steps(Settings(ollama_url=""))[2:]  # sin source ni download, sin Ollama
    return [CannedStep("source", source), CannedStep("download", download), *real]


def _pct(mode: dict[str, Any] | None, key: str = "pct_chart") -> str:
    coincidence = mode and mode["coincidencia"]
    if not coincidence:
        return "n/a"
    if key == "pct_chart":
        counts = f" ({coincidence['coinciden']}/{coincidence['secciones_chart']})"
    elif coincidence["secciones_ref"] is None:
        counts = " (vocab.)"
    else:
        counts = f" ({coincidence['cubiertas']}/{coincidence['secciones_ref']})"
    return f"{coincidence[key]:g} %{counts}"


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "| Canción | BPM ref | BPM | error | tonalidad | a: % chart | a: % ref | b: % chart | "
        "b: % ref | t a (s) | t b (s) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for song in SONGS:
        entry = report.get(song.slug)
        if not entry:
            continue
        a, b = entry["a"], entry["b"]
        lines.append(
            f"| {song.title} | {song.bpm_ref:g} | {a['bpm']} | {a['bpm_error_pct']:+} % | "
            f"{a['tonalidad']} | {_pct(a)} | {_pct(a, 'pct_ref')} | {_pct(b)} | "
            f"{_pct(b, 'pct_ref')} | {a['tiempo_s']} | {b['tiempo_s'] if b else '-'} |"
        )
    return "\n".join(lines)


def main() -> None:
    settings = Settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio-dir", type=Path, default=settings.cache_dir / "spike")
    parser.add_argument("--cache-dir", type=Path, default=settings.cache_dir / "validacion")
    parser.add_argument("--json", type=Path, help="escribe el detalle completo acá")
    parser.add_argument("--only", help="slug de una sola canción")
    parser.add_argument(
        "--cifra-file",
        type=Path,
        help="texto de cifra para el modo b (en vez de la fixture); con --only",
    )
    args = parser.parse_args()
    report: dict[str, Any] = {}
    for song in SONGS:
        if args.only and song.slug != args.only:
            continue
        print(f"== {song.title}", file=sys.stderr)
        report[song.slug] = validate_song(
            song, build_steps(song, args.audio_dir), args.cache_dir, args.cifra_file
        )
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(markdown(report))


if __name__ == "__main__":
    main()
