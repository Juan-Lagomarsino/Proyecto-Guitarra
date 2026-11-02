import type { ChartChord, ChartSection, SongChartContent } from '../songs/types'
import { secondsToBeats } from './timeline'

export type BackingVoice = 'kick' | 'snare' | 'hihat' | 'bass' | 'chord'

/** Evento del arreglo. `beat` y `durBeats` en beats; `velocity` entre 0 y 1. */
export interface BackingEvent {
  beat: number
  durBeats: number
  voice: BackingVoice
  midi?: number | number[]
  velocity: number
}

export interface BeatRange {
  /** Inclusivo. */
  fromBeat: number
  /** Exclusivo. */
  toBeat: number
}

interface DrumHit {
  voice: 'kick' | 'snare' | 'hihat'
  at: number
  dur: number
  velocity: number
}

interface BarPattern {
  beatsPerBar: number
  hits: DrumHit[]
}

const hihats = (count: number, step: number, accentEvery: number): DrumHit[] =>
  Array.from({ length: count }, (_, i) => ({
    voice: 'hihat',
    at: i * step,
    dur: step,
    velocity: i % accentEvery === 0 ? 0.5 : 0.35,
  }))

const hit = (
  voice: DrumHit['voice'],
  at: number,
  velocity: number,
): DrumHit => ({
  voice,
  at,
  dur: 0.25,
  velocity,
})

const PATTERNS: Record<string, BarPattern> = {
  '4/4': {
    beatsPerBar: 4,
    hits: [
      hit('kick', 0, 0.9),
      hit('kick', 2, 0.8),
      hit('snare', 1, 0.8),
      hit('snare', 3, 0.8),
      ...hihats(8, 0.5, 2),
    ],
  },
  '3/4': {
    beatsPerBar: 3,
    hits: [
      hit('kick', 0, 0.9),
      hit('snare', 1, 0.7),
      hit('snare', 2, 0.7),
      ...hihats(6, 0.5, 2),
    ],
  },
  // En 6/8 el beat de la grilla es la negra con puntillo: 2 beats por compás.
  '6/8': {
    beatsPerBar: 2,
    hits: [hit('kick', 0, 0.9), hit('snare', 1, 0.8), ...hihats(6, 1 / 3, 3)],
  },
}

const DEFAULT_SIGNATURE = '4/4'
const patternFor = (signature: string | undefined): BarPattern =>
  PATTERNS[signature ?? DEFAULT_SIGNATURE] ?? PATTERNS[DEFAULT_SIGNATURE]

// ---------------------------------------------------------------- acordes

const NOTE_PITCH: Record<string, number> = {
  C: 0,
  D: 2,
  E: 4,
  F: 5,
  G: 7,
  A: 9,
  B: 11,
}
/** Afinación estándar, de la cuerda 6 a la 1 (E2 A2 D3 G3 B3 E4). */
const STANDARD_TUNING = [40, 45, 50, 55, 59, 64]
const BASS_BASE_MIDI = 36 // C2: las fundamentales caen en 36..47 (octavas 2-3)
const CHORD_BASE_MIDI = 48 // C3

const NO_CHORD = /^(N\.?C\.?|N)$/i

export interface ParsedChord {
  root: number
  bass: number
  intervals: number[]
}

function pitchClass(note: string): number | undefined {
  const base = NOTE_PITCH[note[0]]
  if (base === undefined) return undefined
  const shift = note.endsWith('#') ? 1 : note.endsWith('b') ? -1 : 0
  return (base + shift + 12) % 12
}

function triadIntervals(quality: string): number[] {
  if (/^(dim|°)/.test(quality)) return [0, 3, 6]
  if (/^(aug|\+)/.test(quality)) return [0, 4, 8]
  if (/^sus2/.test(quality)) return [0, 2, 7]
  if (/^sus/.test(quality)) return [0, 5, 7]
  if (/^(m(?!aj)|min|-)/.test(quality)) return [0, 3, 7]
  return [0, 4, 7]
}

/** Interpreta un nombre ("F#m7", "C/G"); `null` si es N.C. o no se entiende. */
export function parseChordName(name: string): ParsedChord | null {
  const trimmed = name.trim()
  if (NO_CHORD.test(trimmed)) return null
  const match = /^([A-G][#b]?)([^/]*)(?:\/([A-G][#b]?))?$/.exec(trimmed)
  if (!match) return null
  const root = pitchClass(match[1])
  if (root === undefined) return null
  const bass = match[3] ? (pitchClass(match[3]) ?? root) : root
  return { root, bass, intervals: triadIntervals(match[2]) }
}

/** Notas MIDI de una forma relativa al capo (cuerda 6 a 1, `'x'` = muda). */
export function shapeMidi(shape: ChartChord['shape'], capo = 0): number[] {
  return shape.flatMap((fret, i) =>
    fret === 'x' ? [] : [STANDARD_TUNING[i] + fret + capo],
  )
}

function chordMidi(
  chord: ChartChord,
  parsed: ParsedChord,
  capo: number,
): number[] {
  const fromShape = shapeMidi(chord.shape, capo)
  if (fromShape.length > 0) return fromShape
  return parsed.intervals.map((i) => CHORD_BASE_MIDI + parsed.root + i)
}

// ---------------------------------------------------------------- tiempo

type ToBeats = (tS: number) => number

function beatConverter(content: SongChartContent): ToBeats {
  const grid = content.beat_grid
  if (grid && grid.beats_s.length >= 2)
    return (tS) => secondsToBeats(tS, grid.beats_s)
  const beatsPerSecond = content.bpm / 60
  return (tS) => tS * beatsPerSecond
}

/** Inicio (en beats) de cada compás que toca [0, endBeat). */
function barStarts(
  content: SongChartContent,
  toBeats: ToBeats,
  beatsPerBar: number,
  endBeat: number,
): number[] {
  const downbeats = content.beat_grid?.downbeats_s ?? []
  const known = [...new Set(downbeats.map((t) => Math.round(toBeats(t))))].sort(
    (a, b) => a - b,
  )
  const first = known[0] ?? 0
  const last = known[known.length - 1] ?? 0
  const starts = new Set<number>(known.length > 0 ? known : [0])
  for (let s = first - beatsPerBar; s + beatsPerBar > 0; s -= beatsPerBar)
    starts.add(s)
  for (let s = last + beatsPerBar; s < endBeat; s += beatsPerBar) starts.add(s)
  return [...starts].filter((s) => s < endBeat).sort((a, b) => a - b)
}

// ---------------------------------------------------------------- generador

const VOICE_ORDER: BackingVoice[] = ['kick', 'snare', 'hihat', 'bass', 'chord']

interface Span {
  start: number
  end: number
}

function drumEvents(
  sections: Span[],
  bars: number[],
  pattern: BarPattern,
): BackingEvent[] {
  const events: BackingEvent[] = []
  bars.forEach((barStart, i) => {
    const barEnd = bars[i + 1] ?? barStart + pattern.beatsPerBar
    for (const h of pattern.hits) {
      const beat = barStart + h.at
      if (beat >= barEnd || beat < 0) continue
      if (!sections.some((s) => beat >= s.start && beat < s.end)) continue
      events.push({
        beat,
        durBeats: h.dur,
        voice: h.voice,
        velocity: h.velocity,
      })
    }
  })
  return events
}

interface ChordSpan extends Span {
  chord: ChartChord
  parsed: ParsedChord
}

function chordSpans(
  section: ChartSection,
  toBeats: ToBeats,
  sectionEnd: number,
): ChordSpan[] {
  const chords = [...(section.chords ?? [])].sort((a, b) => a.t_s - b.t_s)
  return chords.flatMap((chord, i) => {
    const parsed = parseChordName(chord.name)
    if (!parsed) return []
    const next = chords[i + 1]
    const end = Math.min(next ? toBeats(next.t_s) : sectionEnd, sectionEnd)
    const start = toBeats(chord.t_s)
    return end > start ? [{ start, end, chord, parsed }] : []
  })
}

/** Puntos donde se vuelve a tocar dentro del acorde: su inicio y cada comienzo de compás. */
const attackPoints = (span: Span, bars: number[]): number[] => [
  span.start,
  ...bars.filter((b) => b > span.start && b < span.end),
]

function harmonyEvents(
  spans: ChordSpan[],
  bars: number[],
  beatsPerBar: number,
  capo: number,
): BackingEvent[] {
  const events: BackingEvent[] = []
  for (const span of spans) {
    const points = attackPoints(span, bars)
    points.forEach((beat, i) => {
      const durBeats = (points[i + 1] ?? span.end) - beat
      const onBar = bars.includes(beat)
      events.push({
        beat,
        durBeats,
        voice: 'chord',
        midi: chordMidi(span.chord, span.parsed, capo),
        velocity: onBar ? 0.6 : 0.5,
      })
      events.push({
        beat,
        durBeats: Math.min(durBeats, beatsPerBar),
        voice: 'bass',
        midi: BASS_BASE_MIDI + span.parsed.bass,
        velocity: onBar ? 0.8 : 0.7,
      })
    })
  }
  return events
}

const inRange = (beat: number, range?: BeatRange): boolean =>
  !range || (beat >= range.fromBeat && beat < range.toBeat)

/** Arreglo del backing (batería + bajo + acordes) a partir del chart de un instrumento. */
export function generateArrangement(
  content: SongChartContent,
  range?: BeatRange,
): BackingEvent[] {
  const toBeats = beatConverter(content)
  const pattern = patternFor(content.time_signature)
  const sections = content.sections.map((source) => ({
    start: toBeats(source.start_s),
    end: toBeats(source.end_s),
    source,
  }))
  const endBeat = Math.max(0, ...sections.map((s) => s.end))
  const bars = barStarts(content, toBeats, pattern.beatsPerBar, endBeat)

  const events = [
    ...drumEvents(sections, bars, pattern),
    ...sections.flatMap((s) =>
      harmonyEvents(
        chordSpans(s.source, toBeats, s.end),
        bars,
        pattern.beatsPerBar,
        content.capo ?? 0,
      ),
    ),
  ]
  return events
    .filter((e) => inRange(e.beat, range))
    .sort(
      (a, b) =>
        a.beat - b.beat ||
        VOICE_ORDER.indexOf(a.voice) - VOICE_ORDER.indexOf(b.voice),
    )
}
