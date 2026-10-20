import type { Notation } from './types'

export type Tuning = NonNullable<Notation['tuning']>

/** Afinación estándar, de la cuerda 6 (grave) a la 1 (aguda). */
export const STANDARD_TUNING: Tuning = ['E2', 'A2', 'D3', 'G3', 'B3', 'E4']

const NATURALS: Record<string, number> = {
  C: 0,
  D: 2,
  E: 4,
  F: 5,
  G: 7,
  A: 9,
  B: 11,
}

const NOTE_NAME = /^([A-G])([#b]?)/

/** Clase de altura (0 = C … 11 = B) de un nombre de nota, con o sin octava. */
export function pitchClass(name: string): number {
  const match = NOTE_NAME.exec(name)
  if (!match) throw new Error(`Nota inválida: ${name}`)
  const [, letter, accidental] = match
  const shift = accidental === '#' ? 1 : accidental === 'b' ? -1 : 0
  return (NATURALS[letter] + shift + 12) % 12
}

/** Clase de altura que suena en (cuerda, traste). Cuerda 1 = la e aguda. */
export function noteAt(tuning: Tuning, string: number, fret: number): number {
  if (!Number.isInteger(string) || string < 1 || string > 6) {
    throw new Error(`Cuerda fuera de rango: ${string}`)
  }
  return (((pitchClass(tuning[6 - string]) + fret) % 12) + 12) % 12
}

/** Compara una clase de altura con un nombre de nota, resolviendo enarmónicos. Un nombre inválido no coincide. */
export function sameNote(pitch: number, name: string): boolean {
  try {
    return pitch === pitchClass(name)
  } catch {
    return false
  }
}
