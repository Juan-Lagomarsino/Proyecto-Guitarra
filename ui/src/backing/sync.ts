import type { Notation } from '../notation/types'
import type {
  BeatGrid,
  ChartChord,
  ChartSection,
  SectionStrum,
} from '../songs/types'
import { gridBeatsPerBar } from './arrangement'
import { secondsToBeats } from './timeline'

const SECONDS_PER_MINUTE = 60

/** Sección que suena en `position`: start_s <= position < end_s (el límite pertenece a la siguiente). */
export function activeSection(
  position: number,
  sections: readonly ChartSection[],
): ChartSection | null {
  return (
    sections.find((s) => position >= s.start_s && position < s.end_s) ?? null
  )
}

/** Índice del acorde vigente: el último con t_s <= position. `null` si aún no empezó o no hay acordes. */
export function activeChordIndex(
  position: number,
  chords: readonly ChartChord[] | undefined,
): number | null {
  let found: number | null = null
  chords?.forEach((chord, index) => {
    if (chord.t_s > position) return
    if (found === null || chord.t_s >= chords[found].t_s) found = index
  })
  return found
}

/** Beat de la canción en `position`: con `beat_grid` interpola; sin grilla usa el bpm fijo. */
export function songBeat(
  position: number,
  grid: BeatGrid | null | undefined,
  bpm: number,
): number {
  if (grid && grid.beats_s.length >= 2) {
    return secondsToBeats(position, grid.beats_s)
  }
  return (position * bpm) / SECONDS_PER_MINUTE
}

/** Beat relativo al inicio de la sección; `null` si `position` cae fuera de ella. */
export function sectionBeat(
  position: number,
  section: Pick<ChartSection, 'start_s' | 'end_s'>,
  grid: BeatGrid | null | undefined,
  bpm: number,
): number | null {
  if (position < section.start_s || position >= section.end_s) return null
  return songBeat(position, grid, bpm) - songBeat(section.start_s, grid, bpm)
}

/**
 * Golpe del patrón que suena en `beat` (relativo al inicio de la sección, el mismo
 * origen que usa la API para los beats del ejercicio). El patrón
 * reparte sus celdas en partes iguales de `beats_per_cycle` (o del compás de la grilla).
 */
export function activeStrumIndex(
  beat: number,
  strum: Pick<SectionStrum, 'pattern' | 'beats_per_cycle'>,
  timeSignature?: string,
): number | null {
  const cells = strum.pattern.length
  const cycle = strum.beats_per_cycle ?? gridBeatsPerBar(timeSignature)
  if (cells === 0 || beat < 0 || cycle <= 0) return null
  const phase = (beat % cycle) / cycle
  return Math.min(Math.floor(phase * cells), cells - 1)
}

/** Índices de los eventos de la notación que suenan en `beat`: t <= beat < t + dur. */
export function activeEventIndices(
  notation: Pick<Notation, 'events'>,
  beat: number,
): number[] {
  const indices: number[] = []
  notation.events?.forEach((event, index) => {
    if (event.t <= beat && beat < event.t + event.dur) indices.push(index)
  })
  return indices
}
