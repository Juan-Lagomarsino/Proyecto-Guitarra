import { describe, expect, it } from 'vitest'
import type { NoteEvent } from '../notation/types'
import {
  beatsToSeconds,
  endBeat,
  findActiveGroup,
  groupEvents,
  isDownbeat,
  parseBarLength,
  secondsToBeats,
} from './timing'

const ev = (t: number, dur = 1): NoteEvent => ({ t, dur, string: 1, fret: 0 })

describe('conversión beats/segundos', () => {
  it('a 120 bpm un beat dura medio segundo', () => {
    expect(beatsToSeconds(1, 120)).toBeCloseTo(0.5)
    expect(secondsToBeats(0.5, 120)).toBeCloseTo(1)
  })
})

describe('groupEvents', () => {
  it('agrupa eventos simultáneos y ordena por t, conservando índices originales', () => {
    const groups = groupEvents([ev(1), ev(0), ev(1, 2)])
    expect(groups).toEqual([
      { t: 0, end: 1, indices: [1] },
      { t: 1, end: 3, indices: [0, 2] },
    ])
  })

  it('lista vacía da sin grupos', () => {
    expect(groupEvents([])).toEqual([])
    expect(endBeat([])).toBe(0)
  })
})

describe('findActiveGroup', () => {
  const groups = groupEvents([ev(0), ev(1), ev(3)])
  it('devuelve -1 antes del primer evento y al terminar', () => {
    expect(findActiveGroup(groups, -1)).toBe(-1)
    expect(findActiveGroup(groups, 4)).toBe(-1)
  })
  it('devuelve el último grupo iniciado, también en huecos', () => {
    expect(findActiveGroup(groups, 0)).toBe(0)
    expect(findActiveGroup(groups, 0.99)).toBe(0)
    expect(findActiveGroup(groups, 1)).toBe(1)
    expect(findActiveGroup(groups, 2.5)).toBe(1)
    expect(findActiveGroup(groups, 3.5)).toBe(2)
  })
})

describe('compás', () => {
  it('parsea el compás en beats de negra', () => {
    expect(parseBarLength('3/4')).toBe(3)
    expect(parseBarLength('4/4')).toBe(4)
    expect(parseBarLength('6/8')).toBe(3)
    expect(parseBarLength(undefined)).toBe(4)
    expect(parseBarLength('basura')).toBe(4)
  })
  it('detecta el 1 del compás', () => {
    expect(isDownbeat(0, 3)).toBe(true)
    expect(isDownbeat(3, 3)).toBe(true)
    expect(isDownbeat(4, 3)).toBe(false)
    expect(isDownbeat(-3, 3)).toBe(true)
    expect(isDownbeat(-2, 3)).toBe(false)
  })
})
