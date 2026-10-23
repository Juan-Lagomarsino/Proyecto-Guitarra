"""Paso de armado: junta las salidas de todos los pasos en el resultado que espera la API.

Entradas (salidas previas, todas por nombre de paso): `source`, `download`, `tempo`, `structure`,
`chords`, `key`, `cifraclub` y `strum`. Salida: el cuerpo de `POST /jobs/{id}/result`
(`{metadata, sections, charts}`, ver `AnalysisResult` en la API), con un `SongChart` por
instrumento (clásica y eléctrica) que cumple el esquema de ADR 0008.

Decisiones:
- Sin BPM (tempo sin beats) no hay chart posible: error permanente con un mensaje claro.
- Sin secciones de estructura, una sola sección con toda la canción.
- Acordes: los de BTC por sección; si la cifra pegada alinea bien (domain/alignment.py) los
  nombres salen de Cifra Club con los tiempos detectados y la confianza mezclada.
- Formas por instrumento con `guitarra_core`; clásica usa el capo de la cifra o el que sugiere el
  core. El rasgueo (y el arpegio, solo clásica) es uno por canción y se copia a cada sección.
- La confianza de la estructura ("baja"/"media") no tiene campo en el chart: no se vuelca.
"""

from typing import Any

from guitarra_core.chord_shapes import ChordShape
from guitarra_core.instrument import Instrument, best_capo, voicings_for

from guitarra_worker.domain.chart_assembly import (
    TIME_DECIMALS,
    CifraMatch,
    SectionPlan,
    match_with_cifra,
    merge_detected,
    plan_sections,
    section_drafts,
    section_id,
)
from guitarra_worker.pipeline.step import PermanentStepError, PipelineContext

MAX_CAPO = 12
INSTRUMENTS: tuple[Instrument, ...] = ("classical", "electric")
TOOLS = {
    "source": "yt-dlp",
    "tempo": "beat_this",
    "structure": "librosa",
    "chords": "btc",
    "key": "krumhansl-schmuckler",
    "cifraclub": "cifraclub-texto",
    "strum": "reglas",
}
DEFAULT_VERSION = "1"


def _seconds(value: float) -> float:
    return round(float(value), TIME_DECIMALS)


class AssembleStep:
    name = "assemble"
    version = "1"

    def __init__(self, step_versions: dict[str, str] | None = None) -> None:
        self._versions = step_versions or {}

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        outputs = ctx.outputs
        tempo = outputs.get("tempo") or {}
        if not tempo.get("bpm"):
            raise PermanentStepError(
                "No pude detectar el tempo de la canción: no hay chart posible"
            )
        ctx.progress("Armando el chart")
        detected = merge_detected((outputs.get("chords") or {}).get("chords", []))
        match = match_with_cifra(outputs.get("cifraclub"), detected)
        try:
            drafts = section_drafts(
                (outputs.get("structure") or {}).get("sections", []), _song_end(outputs, detected)
            )
        except ValueError as error:
            raise PermanentStepError(str(error)) from error
        plans = plan_sections(drafts, detected, match)
        ids = [section_id(plan.name, index) for index, plan in enumerate(plans)]
        return {
            "metadata": self._metadata(ctx),
            "sections": [_section_result(plan, ids[i], i) for i, plan in enumerate(plans)],
            "charts": [
                self._chart(instrument, plans, ids, outputs, match) for instrument in INSTRUMENTS
            ],
        }

    def _metadata(self, ctx: PipelineContext) -> dict[str, Any]:
        source = ctx.outputs.get("source") or {}
        download = ctx.outputs.get("download") or {}
        key = (ctx.outputs.get("key") or {}).get("key")
        metadata: dict[str, Any] = {
            "bpm": ctx.outputs["tempo"]["bpm"],
            "key": key["name"] if key else None,
            "duration_s": download.get("duration_s") or source.get("duration_s"),
            "year": source.get("year"),
            "youtube_id": source.get("youtube_id"),
        }
        if not ctx.job.title:
            metadata["title"] = source.get("title")
        if not ctx.job.artist:
            metadata["artist"] = source.get("artist")
        return {k: v for k, v in metadata.items() if v}

    def _chart(
        self,
        instrument: Instrument,
        plans: list[SectionPlan],
        ids: list[str],
        outputs: dict[str, dict[str, Any]],
        match: CifraMatch | None,
    ) -> dict[str, Any]:
        tempo = outputs["tempo"]
        capo = _capo_for(instrument, plans, outputs.get("cifraclub"), match)
        shaped = _shaped_chords(instrument, plans, capo)
        strum, arpeggio = _strum_parts(outputs.get("strum"), instrument)
        sections = [
            _chart_section(plan, ids[i], i, shaped[i], strum, arpeggio)
            for i, plan in enumerate(plans)
        ]
        chart: dict[str, Any] = {
            "instrument": instrument,
            "key": _key_part(outputs.get("key")),
            "bpm": tempo["bpm"],
            "time_signature": f"{tempo.get('beats_per_bar') or 4}/4",
            "capo": capo,
            "beat_grid": _beat_grid(tempo),
            "sections": sections,
            "sources": self._sources(outputs, match, strum),
        }
        return {k: v for k, v in chart.items() if v is not None}

    def _sources(
        self, outputs: dict[str, dict[str, Any]], match: CifraMatch | None, strum: Any
    ) -> list[dict[str, str]]:
        used = ["source", "tempo"]
        used += ["structure"] if (outputs.get("structure") or {}).get("sections") else []
        used += ["chords"]
        used += ["key"] if (outputs.get("key") or {}).get("key") else []
        used += ["cifraclub"] if match else []
        used += ["strum"] if strum else []
        tools = dict(TOOLS)
        tools["chords"] = (outputs.get("chords") or {}).get("model") or TOOLS["chords"]
        if strum:
            tools["strum"] = strum["source"]
        return [
            {"step": s, "tool": tools[s], "version": self._versions.get(s, DEFAULT_VERSION)}
            for s in used
            if s in outputs
        ]


def _song_end(outputs: dict[str, dict[str, Any]], detected: list[Any]) -> float:
    duration = (outputs.get("download") or {}).get("duration_s")
    if duration:
        return float(duration)
    beats = outputs["tempo"].get("beats") or []
    return max([detected[-1].end if detected else 0.0, beats[-1] if beats else 0.0])


def _section_result(plan: SectionPlan, slug: str, position: int) -> dict[str, Any]:
    return {
        "slug": slug,
        "name": plan.name,
        "start_s": _seconds(plan.start_s),
        "end_s": _seconds(plan.end_s),
        "position": position,
    }


def _capo_for(
    instrument: Instrument,
    plans: list[SectionPlan],
    cifra: dict[str, Any] | None,
    match: CifraMatch | None,
) -> int:
    if instrument != "classical":
        return 0
    if match and cifra:
        return min(max(int(cifra.get("capo") or 0), 0), MAX_CAPO)
    progression = [chord.name for plan in plans for chord in plan.chords]
    return best_capo(progression).capo if progression else 0


def _shaped_chords(
    instrument: Instrument, plans: list[SectionPlan], capo: int
) -> list[list[tuple[Any, ChordShape]]]:
    """Por sección, los acordes con forma; los que no tienen forma posible se omiten."""
    flat = [chord for plan in plans for chord in plan.chords]
    voicings = iter(voicings_for([c.name for c in flat], instrument, capo, False))
    shaped: list[list[tuple[Any, ChordShape]]] = []
    for plan in plans:
        pairs = [(chord, next(voicings)) for chord in plan.chords]
        shaped.append([(c, v) for c, v in pairs if v.shape is not None])
    return shaped


def _chart_section(
    plan: SectionPlan,
    slug: str,
    order: int,
    shaped: list[tuple[Any, Any]],
    strum: dict[str, Any] | None,
    arpeggio: dict[str, Any] | None,
) -> dict[str, Any]:
    section: dict[str, Any] = {
        "id": slug,
        "name": plan.name,
        "start_s": _seconds(plan.start_s),
        "end_s": _seconds(plan.end_s),
        "order": order,
        "chord_source": plan.chord_source,
        "chords": [
            {
                "t_s": _seconds(chord.t_s),
                "name": voicing.chord,
                **voicing.shape.to_notation(),
                "confidence": round(chord.confidence, 3),
            }
            for chord, voicing in shaped
        ],
    }
    if strum:
        section["strum"] = {k: v for k, v in strum.items() if k != "source"}
    if arpeggio:
        section["arpeggio"] = dict(arpeggio)
    return section


def _strum_parts(
    strum_output: dict[str, Any] | None, instrument: Instrument
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    output = strum_output or {}
    strum, arpeggio = output.get("strum"), output.get("arpeggio")
    strum_part = (
        {
            "pattern": strum["pattern"],
            "accent": list(strum["accent"]),
            "beats_per_cycle": strum["beats_per_cycle"],
            "pattern_id": strum["pattern_id"],
            "confidence": strum["confidence"],
            "source": strum["source"],
        }
        if strum
        else None
    )
    arpeggio_part = (
        {
            "pattern_id": arpeggio["pattern_id"],
            "pattern": arpeggio["pattern"],
            "confidence": arpeggio["confidence"],
        }
        if arpeggio and instrument == "classical"
        else None
    )
    return strum_part, arpeggio_part


def _key_part(key_output: dict[str, Any] | None) -> dict[str, Any] | None:
    key = (key_output or {}).get("key")
    if not key:
        return None
    return {"tonic": key["tonic"], "mode": key["mode"], "confidence": key["confidence"]}


def _beat_grid(tempo: dict[str, Any]) -> dict[str, Any] | None:
    beats = tempo.get("beats") or []
    if len(beats) < 2:
        return None
    return {"beats_s": list(beats), "downbeats_s": list(tempo.get("downbeats") or [])}
