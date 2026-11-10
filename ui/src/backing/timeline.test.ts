import { describe, expect, it } from 'vitest'
import { beatsToSeconds, secondsToBeats } from './timeline'

describe('secondsToBeats', () => {
  it.each([
    [0.0, 0.0],
    [0.5, 1.0],
    [0.25, 0.5],
    [1.0, 2.0],
  ])('tempo constante: %d s -> %d beats', (t, expected) => {
    expect(secondsToBeats(t, [0, 0.5, 1, 1.5])).toBeCloseTo(expected)
  })

  it('sigue la deriva del tempo', () => {
    const grid = [0, 0.5, 1.1, 1.8]
    expect(secondsToBeats(0.8, grid)).toBeCloseTo(1.5)
    expect(secondsToBeats(1.1, grid)).toBeCloseTo(2.0)
  })

  it('extrapola con el último intervalo', () => {
    expect(secondsToBeats(1.7, [0, 0.5, 1.1])).toBeCloseTo(3.0)
    expect(secondsToBeats(2.0, [0, 0.5, 1.1])).toBeCloseTo(2 + 0.9 / 0.6)
  })

  it('extrapola antes del primer beat', () => {
    expect(secondsToBeats(-0.25, [0, 0.5, 1])).toBeCloseTo(-0.5)
  })
})

describe('beatsToSeconds', () => {
  it.each([
    [0, 0],
    [1, 0.5],
    [0.5, 0.25],
    [3, 1.5],
  ])('tempo constante: %d beats -> %d s', (beat, expected) => {
    expect(beatsToSeconds(beat, [0, 0.5, 1, 1.5])).toBeCloseTo(expected)
  })

  it('sigue la deriva del tempo', () => {
    const grid = [0, 0.5, 1.1, 1.8]
    expect(beatsToSeconds(1.5, grid)).toBeCloseTo(0.8)
    expect(beatsToSeconds(2, grid)).toBeCloseTo(1.1)
  })

  it('extrapola con el borde en ambos lados', () => {
    expect(beatsToSeconds(3, [0, 0.5, 1.1])).toBeCloseTo(1.7)
    expect(beatsToSeconds(-1, [0, 0.5, 1])).toBeCloseTo(-0.5)
  })

  it('es la inversa de secondsToBeats', () => {
    const grid = [0, 0.4, 0.9, 1.5, 2.2]
    for (const t of [-0.3, 0, 0.7, 1.5, 2.0, 3.1]) {
      expect(beatsToSeconds(secondsToBeats(t, grid), grid)).toBeCloseTo(t)
    }
  })

  it('exige al menos 2 beats', () => {
    expect(() => beatsToSeconds(1, [0])).toThrow()
  })
})
