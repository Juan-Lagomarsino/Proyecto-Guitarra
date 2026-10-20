import type { NoteEvent } from '../notation/types'

/** Funciones puras de tiempo. `t` y `dur` están en beats (negras). */

export interface EventGroup {
  /** Beat de inicio del grupo. */
  t: number
  /** Beat en que termina el evento más largo del grupo. */
  end: number
  /** Índices en `notation.events`, en orden original. */
  indices: number[]
}

const SAME_BEAT_EPSILON = 1e-9
const DEFAULT_BAR_LENGTH = 4

export function beatsToSeconds(beats: number, bpm: number): number {
  return (beats * 60) / bpm
}

export function secondsToBeats(seconds: number, bpm: number): number {
  return (seconds * bpm) / 60
}

/** Agrupa eventos simultáneos (mismo `t`) y ordena los grupos por `t`. */
export function groupEvents(events: readonly NoteEvent[]): EventGroup[] {
  const order = events
    .map((_, i) => i)
    .sort((a, b) => events[a].t - events[b].t || a - b)
  const groups: EventGroup[] = []
  for (const index of order) {
    const { t, dur } = events[index]
    const last = groups[groups.length - 1]
    if (last && Math.abs(last.t - t) < SAME_BEAT_EPSILON) {
      last.indices.push(index)
      last.end = Math.max(last.end, t + dur)
    } else {
      groups.push({ t, end: t + dur, indices: [index] })
    }
  }
  return groups
}

export function endBeat(groups: readonly EventGroup[]): number {
  return groups.reduce((max, g) => Math.max(max, g.end), 0)
}

/**
 * Índice del grupo activo en `beat`: el último que ya empezó (se sostiene
 * en los huecos hasta que arranca el siguiente). -1 antes del primero y
 * desde el fin del ejercicio.
 */
export function findActiveGroup(
  groups: readonly EventGroup[],
  beat: number,
): number {
  if (groups.length === 0 || beat >= endBeat(groups)) return -1
  let found = -1
  for (let i = 0; i < groups.length && groups[i].t <= beat; i++) found = i
  return found
}

/** Largo del compás en beats de negra: 3/4 -> 3, 4/4 -> 4, 6/8 -> 3. */
export function parseBarLength(timeSignature: string | undefined): number {
  const match = /^(\d+)\/(\d+)$/.exec(timeSignature ?? '')
  if (!match) return DEFAULT_BAR_LENGTH
  const length = (Number(match[1]) * 4) / Number(match[2])
  return length > 0 ? length : DEFAULT_BAR_LENGTH
}

/** True si `beat` cae en el 1 de un compás de `barLength` beats. */
export function isDownbeat(beat: number, barLength: number): boolean {
  const rest = ((beat % barLength) + barLength) % barLength
  return rest < SAME_BEAT_EPSILON || barLength - rest < SAME_BEAT_EPSILON
}
