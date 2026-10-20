import { describe, expect, it } from 'vitest'
import { FakeClock, RecordingSink } from './fakeClock'
import { Metronome } from './metronome'

function setup(barLength: number, bpm = 120) {
  const clock = new FakeClock()
  const sink = new RecordingSink(clock)
  const metronome = new Metronome(clock, sink, barLength)
  const secondsPerBeat = 60 / bpm
  metronome.start(
    (beat) => beat * secondsPerBeat,
    0,
    () => true,
  )
  return { clock, sink, metronome }
}

describe('Metronome', () => {
  it('acentúa el 1 en 4/4', () => {
    const { clock, sink } = setup(4)
    clock.advance(4.2)
    const accents = sink.clicks.slice(0, 8).map((c) => c.accent)
    expect(accents).toEqual([
      true,
      false,
      false,
      false,
      true,
      false,
      false,
      false,
    ])
  })

  it('acentúa el 1 en 3/4', () => {
    const { clock, sink } = setup(3)
    clock.advance(3.2)
    const accents = sink.clicks.slice(0, 6).map((c) => c.accent)
    expect(accents).toEqual([true, false, false, true, false, false])
  })

  it('programa los clics en los tiempos del reloj, con anticipación', () => {
    const { clock, sink } = setup(4)
    clock.advance(0.05)
    expect(sink.clicks.map((c) => c.time)).toContain(0)
    clock.advance(1)
    expect(sink.clicks.map((c) => c.time).slice(0, 3)).toEqual([0, 0.5, 1])
    expect(Math.max(...sink.clicks.map((c) => c.time))).toBeLessThanOrEqual(
      clock.now() + 0.2,
    )
  })

  it('no repite clics ni suena tras stop', () => {
    const { clock, sink, metronome } = setup(4)
    clock.advance(2)
    const count = sink.clicks.length
    expect(new Set(sink.clicks.map((c) => c.time)).size).toBe(count)
    metronome.stop()
    clock.advance(5)
    expect(sink.clicks.length).toBe(count)
  })

  it('respeta shouldClick', () => {
    const clock = new FakeClock()
    const sink = new RecordingSink(clock)
    const m = new Metronome(clock, sink, 4)
    m.start(
      (b) => b * 0.5,
      0,
      (b) => b < 2,
    )
    clock.advance(5)
    expect(sink.clicks.length).toBe(2)
  })
})
