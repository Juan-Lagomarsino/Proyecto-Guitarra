import type { NoteEvent } from '../../notation/types'

/** Geometría tomada de drawBoard en docs/referencias/taller-electrica.html. */
export const LEFT = 28
export const FRET_WIDTH = 54
export const STRING_GAP = 24
export const TOP = 14
export const RIGHT_PAD = 6
export const STRING_COUNT = 6
export const BOTTOM_PAD = 36
export const MIN_FRET_SPAN = 8

export type FretRange = [number, number]
export interface Position {
  string: number
  fret: number
}

export const boardWidth = ([lo, hi]: FretRange) =>
  LEFT + (hi - lo + 1) * FRET_WIDTH + RIGHT_PAD
export const boardHeight = () =>
  TOP + (STRING_COUNT - 1) * STRING_GAP + BOTTOM_PAD
export const stringsBottom = () => TOP + (STRING_COUNT - 1) * STRING_GAP

/** Centro horizontal del casillero de un traste. */
export const fretX = (fret: number, [lo]: FretRange) =>
  LEFT + (fret - lo + 0.5) * FRET_WIDTH
/** Borde derecho (el traste metálico) del casillero de un traste. */
export const fretLineX = (fret: number, [lo]: FretRange) =>
  LEFT + (fret - lo + 1) * FRET_WIDTH
/** Cuerda 1 (e aguda) arriba, cuerda 6 abajo. */
export const stringY = (string: number) => TOP + (string - 1) * STRING_GAP

/** Rango de trastes de los eventos con un traste de margen, de al menos 9 trastes. */
export function computeFretRange(events: NoteEvent[]): FretRange {
  if (events.length === 0) return [0, MIN_FRET_SPAN]
  const frets = events.map((event) => event.fret)
  const lo = Math.max(0, Math.min(...frets) - 1)
  const hi = Math.max(lo + MIN_FRET_SPAN, Math.max(...frets) + 1)
  return [lo, hi]
}

/** Posiciones (cuerda, traste) distintas, en orden de aparición. */
export function collectPositions(events: NoteEvent[]): Position[] {
  const seen = new Map<string, Position>()
  for (const { string, fret } of events) {
    const key = `${string}-${fret}`
    if (!seen.has(key)) seen.set(key, { string, fret })
  }
  return [...seen.values()]
}
