import { describe, expect, it } from 'vitest'
import type { Notation } from '../notation/types'
import { FakeAudio } from './fakeClock'
import { PlaybackEngine, type EngineOptions } from './engine'

// 4 eventos; el 1 y el 2 suenan juntos (acorde). 120 bpm: 0.5 s por beat. Fin en el beat 4.
const notation: Notation = {
  bpm: 120,
  time_signature: '4/4',
  events: [
    { t: 0, dur: 1, string: 6, fret: 0 },
    { t: 1, dur: 1, string: 5, fret: 2 },
    { t: 1, dur: 1, string: 4, fret: 2 },
    { t: 2, dur: 2, string: 3, fret: 0 },
  ],
}

function setup(options: Partial<EngineOptions> = {}, n: Notation = notation) {
  const audio = new FakeAudio()
  const engine = new PlaybackEngine(n, { audio: () => audio, ...options })
  return { audio, clock: audio.clock, sink: audio.sink, engine }
}

describe('modo automático', () => {
  it('arranca sin evento activo y detenido', () => {
    const { engine } = setup()
    expect(engine.getSnapshot()).toMatchObject({
      activeIndex: null,
      activeIndices: [],
      isPlaying: false,
      mode: 'auto',
      bpm: 120,
    })
  })

  it('el evento activo sigue t y dur según el bpm', () => {
    const { engine, clock } = setup()
    engine.play()
    clock.advance(0.1)
    expect(engine.getSnapshot().activeIndex).toBe(0)
    clock.advance(0.5) // beat 1.2
    expect(engine.getSnapshot().activeIndices).toEqual([1, 2])
    expect(engine.getSnapshot().activeIndex).toBe(1)
    clock.advance(0.5) // beat 2.2
    expect(engine.getSnapshot().activeIndex).toBe(3)
  })

  it('usa el bpm inicial de las opciones', () => {
    const { engine, clock } = setup({ bpm: 60 })
    engine.play()
    clock.advance(1.1) // beat 1.1 a 60 bpm
    expect(engine.getSnapshot().activeIndex).toBe(1)
  })

  it('cambiar el bpm en vivo mantiene la posición en beats', () => {
    const { engine, clock } = setup()
    engine.play()
    clock.advance(0.75) // beat 1.5
    expect(engine.getSnapshot().activeIndex).toBe(1)
    engine.setBpm(60) // ahora 1 s por beat
    expect(engine.getSnapshot().bpm).toBe(60)
    expect(engine.getSnapshot().activeIndex).toBe(1)
    clock.advance(0.4) // beat 1.9
    expect(engine.getSnapshot().activeIndex).toBe(1)
    clock.advance(0.2) // beat 2.1
    expect(engine.getSnapshot().activeIndex).toBe(3)
  })

  it('ignora bpm inválidos', () => {
    const { engine } = setup()
    engine.setBpm(0)
    engine.setBpm(Number.NaN)
    expect(engine.getSnapshot().bpm).toBe(120)
  })

  it('pausa congela la posición y reanudar continúa desde ahí', () => {
    const { engine, clock } = setup()
    engine.play()
    clock.advance(0.75) // beat 1.5
    engine.pause()
    expect(engine.getSnapshot().isPlaying).toBe(false)
    clock.advance(10)
    expect(engine.getSnapshot().activeIndex).toBe(1)
    engine.play()
    clock.advance(0.3) // beat 2.1
    expect(engine.getSnapshot().activeIndex).toBe(3)
  })

  it('al terminar se detiene, vuelve a null y al inicio', () => {
    const { engine, clock } = setup()
    engine.play()
    clock.advance(2.1) // beat 4.2 > fin (4)
    expect(engine.getSnapshot()).toMatchObject({
      isPlaying: false,
      activeIndex: null,
      activeIndices: [],
    })
    engine.play()
    clock.advance(0.1)
    expect(engine.getSnapshot().activeIndex).toBe(0)
  })

  it('stop vuelve al inicio', () => {
    const { engine, clock } = setup()
    engine.play()
    clock.advance(1)
    engine.stop()
    expect(engine.getSnapshot()).toMatchObject({
      isPlaying: false,
      activeIndex: null,
    })
    engine.play()
    clock.advance(0.1)
    expect(engine.getSnapshot().activeIndex).toBe(0)
  })

  it('sin eventos, play no hace nada', () => {
    const { engine } = setup({}, { bpm: 90 })
    engine.play()
    expect(engine.getSnapshot().isPlaying).toBe(false)
  })
})

describe('modo nota por nota', () => {
  it('no avanza solo y next/prev mueven por grupos', () => {
    const { engine, clock } = setup()
    engine.setMode('step')
    clock.advance(10)
    expect(engine.getSnapshot().activeIndex).toBeNull()
    engine.next()
    expect(engine.getSnapshot().activeIndex).toBe(0)
    engine.next()
    expect(engine.getSnapshot().activeIndices).toEqual([1, 2])
    expect(engine.getSnapshot().activeIndex).toBe(1)
    clock.advance(10)
    expect(engine.getSnapshot().activeIndex).toBe(1)
    engine.next()
    expect(engine.getSnapshot().activeIndex).toBe(3)
    engine.next() // ya es el último: se queda
    expect(engine.getSnapshot().activeIndex).toBe(3)
    engine.prev()
    expect(engine.getSnapshot().activeIndices).toEqual([1, 2])
    engine.prev()
    engine.prev() // ya es el primero: se queda
    expect(engine.getSnapshot().activeIndex).toBe(0)
  })

  it('play no hace sonar nada en nota por nota', () => {
    const { engine, sink, clock } = setup({ metronome: true })
    engine.setMode('step')
    engine.play()
    clock.advance(3)
    expect(engine.getSnapshot().isPlaying).toBe(false)
    expect(sink.clicks).toEqual([])
  })

  it('cambiar de modo detiene la reproducción y conserva el evento', () => {
    const { engine, clock } = setup()
    engine.play()
    clock.advance(0.6)
    engine.setMode('step')
    expect(engine.getSnapshot()).toMatchObject({
      isPlaying: false,
      mode: 'step',
      activeIndex: 1,
    })
    engine.next()
    engine.setMode('auto')
    engine.play()
    clock.advance(0.1) // arranca desde el beat del evento 3 (t = 2)
    expect(engine.getSnapshot().activeIndex).toBe(3)
  })

  it('stop en nota por nota vuelve al inicio', () => {
    const { engine } = setup()
    engine.setMode('step')
    engine.next()
    engine.stop()
    expect(engine.getSnapshot().activeIndex).toBeNull()
  })
})

describe('metrónomo integrado', () => {
  it('no suena si está apagado', () => {
    const { engine, clock, sink } = setup()
    engine.play()
    clock.advance(1)
    expect(sink.clicks).toEqual([])
  })

  it('suena en sincronía con el transporte y acentúa el 1', () => {
    const { engine, clock, sink } = setup({ metronome: true })
    engine.play()
    clock.advance(2.1)
    expect(sink.clicks.map((c) => c.time)).toEqual([0, 0.5, 1, 1.5])
    expect(sink.clicks.map((c) => c.accent)).toEqual([
      true,
      false,
      false,
      false,
    ])
  })

  it('acentúa cada tres beats en 3/4', () => {
    const { engine, clock, sink } = setup(
      { metronome: true },
      { ...notation, time_signature: '3/4' },
    )
    engine.play()
    clock.advance(2.1)
    expect(sink.clicks.map((c) => c.accent)).toEqual([true, false, false, true])
  })

  it('con cambio de bpm los clics siguen la nueva velocidad', () => {
    const { engine, clock, sink } = setup({ metronome: true })
    engine.play()
    clock.advance(0.5) // beat 1
    engine.setBpm(60)
    clock.advance(1.5)
    const times = sink.clicks.map((c) => c.time)
    expect(times).toContain(1.5) // beat 2 = 0.5 s + 1 s
    expect(times).not.toContain(1) // el beat 2 a 120 bpm ya no suena
  })

  it('el compás de entrada suena antes del evento 0 aunque el metrónomo esté apagado', () => {
    const { engine, clock, sink } = setup({ countIn: true })
    engine.play()
    clock.advance(0.1)
    expect(engine.getSnapshot().activeIndex).toBeNull() // todavía contando
    clock.advance(1.95) // 2.05 s = fin del compás de entrada
    expect(engine.getSnapshot().activeIndex).toBe(0)
    expect(sink.clicks.map((c) => c.accent)).toEqual([
      true,
      false,
      false,
      false,
    ])
  })

  it('pause y stop cancelan los clics ya agendados', () => {
    const { engine, clock, sink } = setup({ metronome: true })
    engine.play()
    clock.advance(0.45) // el clic del beat 1 (0.5 s) ya está agendado
    engine.pause()
    expect(sink.cancelled.map((c) => c.time)).toEqual([0.5])
    clock.advance(3)
    expect(sink.clicks.map((c) => c.time)).toEqual([0])

    engine.play() // reanuda en el beat 0.9
    clock.advance(0.01)
    engine.stop()
    expect(sink.cancelled.length).toBe(2)
  })

  it('setBpm cancela lo agendado y no deja clics al tiempo viejo', () => {
    const { engine, clock, sink } = setup({ metronome: true })
    engine.play()
    clock.advance(0.45) // beat 1 agendado en 0.5 a 120 bpm
    engine.setBpm(60) // beat 0.9 hoy: el beat 1 pasa a 0.45 + 0.1 s
    expect(sink.cancelled.map((c) => c.time)).toEqual([0.5])
    clock.advance(1.5)
    const times = sink.clicks.map((c) => c.time)
    expect(times).not.toContain(0.5)
    expect(times[0]).toBe(0)
    expect(times[1]).toBeCloseTo(0.55)
    expect(times[2]).toBeCloseTo(1.55)
    expect(times.length).toBe(3)
  })
})

describe('desmontaje', () => {
  it('dispose cierra el audio, corta timers y un play posterior lo recrea', () => {
    const { engine, audio, clock } = setup({ metronome: true })
    engine.play()
    clock.advance(0.2)
    engine.dispose()
    expect(audio.closed).toBe(1)
    expect(clock.activeTimers).toBe(0)
    engine.play()
    expect(clock.activeTimers).toBeGreaterThan(0)
    engine.dispose()
    expect(audio.closed).toBe(2)
  })
})
