import type { StrumPatternEntry } from '../../api/songs'
import type { ChartSection, SongChartContent } from '../../songs/types'
import {
  patternOptions,
  replaceSection,
  sectionProblem,
  withPattern,
} from './chartEdit'

const intro: ChartSection = {
  id: 'intro',
  name: 'Intro',
  start_s: 0,
  end_s: 10,
  order: 0,
  chord_source: 'detected',
  chords: [
    { t_s: 2, name: 'Am', shape: ['x', 0, 2, 2, 1, 0], confidence: 0.9 },
  ],
}
const verse: ChartSection = {
  id: 'verso',
  name: 'Verso',
  start_s: 10,
  end_s: 30,
  order: 1,
  chord_source: 'detected',
}
const content: SongChartContent = {
  instrument: 'electric',
  bpm: 90,
  time_signature: '4/4',
  sections: [intro, verse],
}

const patterns: StrumPatternEntry[] = [
  entry('rasgueo-4-folk', 'strum', 4, 'D-DU-UDU'),
  entry('rasgueo-3-balada', 'strum', 3, 'D-D-DU'),
  entry('arpegio-4-basico', 'arpeggio', 4, 'p-i-m-i'),
]

function entry(
  id: string,
  kind: 'strum' | 'arpeggio',
  beats: number,
  pattern: string,
): StrumPatternEntry {
  return {
    id,
    name: id,
    kind,
    beats_per_bar: beats,
    style: 'x',
    complexity: 1,
    pattern,
    accent: [0],
    beats_per_cycle: beats,
  }
}

describe('sectionProblem', () => {
  const ok = { name: 'Intro', start_s: 0, end_s: 10 }

  it('acepta una edición válida', () => {
    expect(sectionProblem(content, 'intro', ok)).toBeNull()
  })

  it('pide un nombre', () => {
    expect(sectionProblem(content, 'intro', { ...ok, name: '  ' })).toMatch(
      /nombre/i,
    )
  })

  it('exige que el inicio sea menor que el fin', () => {
    expect(
      sectionProblem(content, 'intro', { ...ok, start_s: 10, end_s: 10 }),
    ).toMatch(/inicio/i)
  })

  it('no deja pisar a la sección vecina', () => {
    expect(sectionProblem(content, 'intro', { ...ok, end_s: 12 })).toMatch(
      /Verso/,
    )
    expect(
      sectionProblem(content, 'verso', {
        name: 'Verso',
        start_s: 8,
        end_s: 30,
      }),
    ).toMatch(/Intro/)
  })

  it('no deja acordes fuera de los límites', () => {
    expect(sectionProblem(content, 'intro', { ...ok, start_s: 3 })).toMatch(
      /acordes/i,
    )
    expect(sectionProblem(content, 'intro', { ...ok, end_s: 2 })).toMatch(
      /acordes/i,
    )
  })
})

describe('replaceSection', () => {
  it('cambia solo esa sección y no muta el original', () => {
    const next = replaceSection(content, 'verso', { name: 'Estrofa' })
    expect(next.sections.map((s) => s.name)).toEqual(['Intro', 'Estrofa'])
    expect(content.sections[1]?.name).toBe('Verso')
  })
})

describe('patternOptions', () => {
  it('filtra por tipo y compases, y conserva el patrón actual', () => {
    const ids = patternOptions(
      patterns,
      'strum',
      '4/4',
      'rasgueo-3-balada',
    ).map((p) => p.id)
    expect(ids).toEqual(['rasgueo-4-folk', 'rasgueo-3-balada'])
  })

  it('con otro compás ofrece los de ese compás', () => {
    const ids = patternOptions(patterns, 'strum', '3/4', null).map((p) => p.id)
    expect(ids).toEqual(['rasgueo-3-balada'])
  })
})

describe('withPattern', () => {
  it('arma el rasgueo del chart con el patrón del catálogo', () => {
    expect(withPattern(patterns[0]!)).toEqual({
      strum: {
        pattern: 'D-DU-UDU',
        accent: [0],
        beats_per_cycle: 4,
        pattern_id: 'rasgueo-4-folk',
        confidence: 1,
      },
    })
  })

  it('arma el arpegio del chart', () => {
    expect(withPattern(patterns[2]!)).toEqual({
      arpeggio: {
        pattern_id: 'arpegio-4-basico',
        pattern: 'p-i-m-i',
        confidence: 1,
      },
    })
  })
})
