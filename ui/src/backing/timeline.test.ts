import { describe, expect, it } from 'vitest'
import { secondsToBeats } from './timeline'

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
