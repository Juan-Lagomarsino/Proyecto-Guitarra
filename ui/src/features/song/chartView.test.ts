import type { ChartChord } from '../../songs/types'
import {
  capoLabel,
  chordTonic,
  formatTime,
  isLowConfidence,
  keyLabel,
  uniqueChords,
} from './chartView'

const chord = (name: string, confidence: number, fret = 2): ChartChord => ({
  t_s: 0,
  name,
  shape: ['x', 0, fret, 2, 1, 0],
  confidence,
})

describe('chartView', () => {
  it('marca baja confianza por debajo del umbral', () => {
    expect(isLowConfidence(0.59)).toBe(true)
    expect(isLowConfidence(0.6)).toBe(false)
  })

  it('formatea tiempos como m:ss', () => {
    expect(formatTime(0)).toBe('0:00')
    expect(formatTime(75.4)).toBe('1:15')
  })

  it('describe tonalidad y capo', () => {
    expect(keyLabel({ tonic: 'A', mode: 'minor', confidence: 1 })).toBe(
      'A menor',
    )
    expect(keyLabel(null)).toBeNull()
    expect(capoLabel(0)).toBe('Sin capo')
    expect(capoLabel(3)).toBe('Capo en 3')
  })

  it('saca la tónica del nombre del acorde', () => {
    expect(chordTonic('F#m7')).toBe('F#')
    expect(chordTonic('Bbmaj7')).toBe('Bb')
    expect(chordTonic('N.C.')).toBeUndefined()
  })

  it('une acordes repetidos y se queda con la menor confianza', () => {
    const result = uniqueChords([
      chord('Am', 0.9),
      chord('C', 0.8, 3),
      chord('Am', 0.4),
    ])
    expect(result.map((u) => u.chord.name)).toEqual(['Am', 'C'])
    expect(result[0].confidence).toBe(0.4)
  })

  it('no une el mismo nombre con distinta digitación', () => {
    expect(
      uniqueChords([chord('Am', 0.9, 2), chord('Am', 0.9, 7)]),
    ).toHaveLength(2)
  })
})
