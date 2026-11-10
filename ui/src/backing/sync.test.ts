import { describe, expect, it } from 'vitest'
import type { ChartChord, ChartSection } from '../songs/types'
import {
  activeChordIndex,
  activeEventIndices,
  activeSection,
  activeStrumIndex,
  sectionBeat,
  songBeat,
} from './sync'

const section = (id: string, start_s: number, end_s: number): ChartSection => ({
  id,
  name: id,
  start_s,
  end_s,
  order: 0,
  chord_source: 'detected',
})
const sections = [section('a', 2, 10), section('b', 10, 20)]
const chord = (t_s: number): ChartChord => ({
  t_s,
  name: 'Am',
  shape: ['x', 0, 2, 2, 1, 0],
  confidence: 1,
})

describe('activeSection', () => {
  it('antes de la primera sección no hay ninguna', () => {
    expect(activeSection(1.9, sections)).toBeNull()
  })
  it('el límite pertenece a la sección que empieza', () => {
    expect(activeSection(2, sections)?.id).toBe('a')
    expect(activeSection(10, sections)?.id).toBe('b')
  })
  it('después de la última no hay ninguna', () => {
    expect(activeSection(20, sections)).toBeNull()
  })
  it('entre secciones separadas no hay ninguna', () => {
    const gap = [section('a', 0, 10), section('b', 12, 20)]
    expect(activeSection(11, gap)).toBeNull()
  })
})

describe('activeChordIndex', () => {
  const chords = [chord(2), chord(4), chord(6)]
  it('toma el último acorde ya empezado', () => {
    expect(activeChordIndex(4, chords)).toBe(1)
    expect(activeChordIndex(5.9, chords)).toBe(1)
    expect(activeChordIndex(9, chords)).toBe(2)
  })
  it('antes del primero no hay', () => {
    expect(activeChordIndex(1, chords)).toBeNull()
  })
  it('sección sin acordes', () => {
    expect(activeChordIndex(3, undefined)).toBeNull()
    expect(activeChordIndex(3, [])).toBeNull()
  })
})

describe('beats', () => {
  const grid = { beats_s: [0, 1, 3] as [number, number, number] }
  it('con grilla interpola', () => {
    expect(songBeat(2, grid, 120)).toBeCloseTo(1.5)
  })
  it('sin grilla usa el bpm', () => {
    expect(songBeat(2, null, 120)).toBeCloseTo(4)
    expect(songBeat(2, undefined, 60)).toBeCloseTo(2)
  })
  it('sectionBeat es relativo al inicio y null fuera de la sección', () => {
    const s = section('a', 1, 3)
    expect(sectionBeat(2, s, grid, 120)).toBeCloseTo(0.5)
    expect(sectionBeat(1, s, grid, 120)).toBe(0)
    expect(sectionBeat(3, s, grid, 120)).toBeNull()
    expect(sectionBeat(0.5, s, grid, 120)).toBeNull()
  })
})

describe('activeStrumIndex', () => {
  const strum = { pattern: 'D-DU-UDU', beats_per_cycle: 4 }
  it('reparte las celdas en el ciclo', () => {
    expect(activeStrumIndex(0, strum)).toBe(0)
    expect(activeStrumIndex(0.5, strum)).toBe(1)
    expect(activeStrumIndex(3.9, strum)).toBe(7)
  })
  it('el ciclo se repite', () => {
    expect(activeStrumIndex(4.5, strum)).toBe(1)
  })
  it('beats_per_cycle distinto del compás', () => {
    expect(activeStrumIndex(1, { pattern: 'DUDU', beats_per_cycle: 2 })).toBe(2)
  })
  it('sin beats_per_cycle usa el compás de la grilla (3/4: 3, 6/8: 2, otro: 4)', () => {
    const noCycle = { pattern: 'DUDU', beats_per_cycle: null }
    expect(activeStrumIndex(1.5, noCycle, '3/4')).toBe(2)
    expect(activeStrumIndex(1, noCycle, '6/8')).toBe(2)
    expect(activeStrumIndex(2, noCycle, '5/4')).toBe(2)
  })
  it('el guion ocupa tiempo y su celda queda activa', () => {
    const dash = { pattern: 'D-DU', beats_per_cycle: 4 }
    expect(activeStrumIndex(1.5, dash)).toBe(1)
  })
  it('beat negativo o patrón vacío no marcan', () => {
    expect(activeStrumIndex(-1, strum)).toBeNull()
    expect(activeStrumIndex(1, { pattern: '', beats_per_cycle: 4 })).toBeNull()
  })
})

describe('activeEventIndices', () => {
  const notation = {
    events: [
      { t: 0, dur: 1, string: 1, fret: 0 },
      { t: 1, dur: 1, string: 2, fret: 1 },
      { t: 1, dur: 2, string: 3, fret: 2 },
    ],
  }
  it('t <= beat < t + dur', () => {
    expect(activeEventIndices(notation, 0)).toEqual([0])
    expect(activeEventIndices(notation, 0.99)).toEqual([0])
    expect(activeEventIndices(notation, 1)).toEqual([1, 2])
    expect(activeEventIndices(notation, 2)).toEqual([2])
    expect(activeEventIndices(notation, 3)).toEqual([])
  })
  it('sin eventos', () => {
    expect(activeEventIndices({}, 0)).toEqual([])
  })
})
