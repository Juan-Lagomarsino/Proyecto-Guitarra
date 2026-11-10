import { describe, expect, it, vi } from 'vitest'
import { FakeClock } from '../playback/fakeClock'
import type { ChartChord, SongChartContent } from '../songs/types'
import { GeneratedBackingSource, type GeneratedMode } from './generatedSource'
import type { SynthVoice, VoiceSink } from './synth'

interface Trigger {
  voice: SynthVoice
  time: number
  durS: number
  midi?: number | number[]
  velocity: number
}

/** Registra los disparos; `cancel()` descarta los que todavía no sonaron. */
class RecordingVoiceSink implements VoiceSink {
  triggers: Trigger[] = []
  cancels = 0
  constructor(private readonly clock: FakeClock) {}
  trigger(
    voice: SynthVoice,
    time: number,
    durS: number,
    midi: number | number[] | undefined,
    velocity: number,
  ): void {
    this.triggers.push({ voice, time, durS, midi, velocity })
  }
  cancel(): void {
    this.cancels++
    this.triggers = this.triggers.filter((t) => t.time <= this.clock.now())
  }
  times(voice?: SynthVoice): number[] {
    return this.triggers
      .filter((t) => voice === undefined || t.voice === voice)
      .map((t) => t.time)
  }
}

const SHAPE_C: ChartChord['shape'] = ['x', 3, 2, 0, 1, 0]
const DURATION = 8

/** 120 bpm: un beat cada 0,5 s; 4 compases de 4/4 en 8 s. */
const chart = (over: Partial<SongChartContent> = {}): SongChartContent => ({
  instrument: 'classical',
  bpm: 120,
  time_signature: '4/4',
  sections: [
    {
      id: 'a',
      name: 'A',
      start_s: 0,
      end_s: DURATION,
      order: 0,
      chord_source: 'user',
      chords: [{ t_s: 0, name: 'C', shape: SHAPE_C, confidence: 0.9 }],
    },
  ],
  ...over,
})

function setup(mode: GeneratedMode, content = chart()) {
  const clock = new FakeClock()
  const sink = new RecordingVoiceSink(clock)
  const source = new GeneratedBackingSource({ content, mode, clock, sink })
  return { clock, sink, source }
}

const expectClose = (actual: number[], expected: number[]) => {
  expect(actual).toHaveLength(expected.length)
  actual.forEach((v, i) => expect(v).toBeCloseTo(expected[i], 6))
}

describe('GeneratedBackingSource - click', () => {
  it('agenda un clic por beat y acentúa el 1 de cada compás', () => {
    const { clock, sink, source } = setup('click')
    source.play()
    clock.advance(4.05)
    expectClose(sink.times(), [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4])
    expectClose(sink.times('accent'), [0, 2, 4])
    expect(
      sink.triggers.every((t) => t.voice === 'click' || t.voice === 'accent'),
    ).toBe(true)
  })

  it('en 6/8 sin downbeats acentúa cada 2 beats de grilla', () => {
    const { clock, sink, source } = setup(
      'click',
      chart({ time_signature: '6/8' }),
    )
    source.play()
    clock.advance(2.05)
    expectClose(sink.times('accent'), [0, 1, 2])
  })

  it('usa los downbeats de la beat_grid', () => {
    const beats = Array.from({ length: 17 }, (_, i) => i * 0.5)
    const content = chart({
      beat_grid: {
        beats_s: beats as [number, number, ...number[]],
        downbeats_s: [0.5, 2.5], // el compás empieza en el beat 1
      },
    })
    const { clock, sink, source } = setup('click', content)
    source.play()
    clock.advance(3)
    expectClose(sink.times('accent'), [0.5, 2.5])
  })

  it('a 50 % cada beat dura el doble de tiempo real', () => {
    const { clock, sink, source } = setup('click')
    source.setRate(0.5)
    source.play()
    clock.advance(2.05)
    expectClose(sink.times(), [0, 1, 2])
    expect(sink.triggers[0].durS).toBeGreaterThan(0)
  })

  it('no emite nada pasado el final de la canción', () => {
    const { clock, sink, source } = setup('click')
    source.play()
    clock.advance(20)
    expect(Math.max(...sink.times())).toBeLessThan(DURATION)
  })
})

describe('GeneratedBackingSource - drums y full', () => {
  it('drums emite solo batería', () => {
    const { clock, sink, source } = setup('drums')
    source.play()
    clock.advance(2)
    const voices = new Set(sink.triggers.map((t) => t.voice))
    expect(voices.has('kick')).toBe(true)
    expect(voices.has('bass')).toBe(false)
    expect(voices.has('chord')).toBe(false)
    expect(voices.has('click')).toBe(false)
  })

  it('full suma bajo y acordes con sus notas', () => {
    const { clock, sink, source } = setup('full')
    source.play()
    clock.advance(0.2)
    const voices = new Set(sink.triggers.map((t) => t.voice))
    for (const v of ['kick', 'hihat', 'bass', 'chord'] as const) {
      expect(voices.has(v)).toBe(true)
    }
    const chord = sink.triggers.find((t) => t.voice === 'chord')
    expect(chord?.midi).toEqual([48, 52, 55, 60, 64])
  })

  it('a 50 % los eventos del arreglo caen al doble de tiempo real', () => {
    const base = setup('drums')
    base.source.play()
    base.clock.advance(1.5)
    const slow = setup('drums')
    slow.source.setRate(0.5)
    slow.source.play()
    slow.clock.advance(3)
    const kicksBase = base.sink.times('kick')
    const kicksSlow = slow.sink.times('kick')
    expect(kicksSlow.length).toBeGreaterThan(0)
    expect(kicksSlow).toHaveLength(kicksBase.length)
    kicksSlow.forEach((t, i) => expect(t).toBeCloseTo(kicksBase[i] * 2, 6))
  })
})

describe('GeneratedBackingSource - transporte', () => {
  it('position sigue al reloj y a la velocidad', () => {
    const { clock, source } = setup('click')
    expect(source.position()).toBe(0)
    source.play()
    clock.advance(1)
    expect(source.position()).toBeCloseTo(1)
    source.setRate(0.5)
    clock.advance(1)
    expect(source.position()).toBeCloseTo(1.5)
    source.pause()
    clock.advance(5)
    expect(source.position()).toBeCloseTo(1.5)
    expect(source.isPlaying()).toBe(false)
  })

  it('acota la velocidad a [0,5; 1]', () => {
    const { clock, source } = setup('click')
    source.setRate(0.1)
    source.play()
    clock.advance(1)
    expect(source.position()).toBeCloseTo(0.5)
    source.setRate(3)
    clock.advance(1)
    expect(source.position()).toBeCloseTo(1.5)
  })

  it('pausa cancela lo agendado y no agenda más', () => {
    const { clock, sink, source } = setup('click')
    source.play()
    clock.advance(0.45) // el clic de 0,5 ya está agendado hacia adelante
    expect(sink.times()).toHaveLength(2)
    source.pause()
    expectClose(sink.times(), [0])
    clock.advance(3)
    expectClose(sink.times(), [0])
  })

  it('reanudar continúa sin repetir eventos', () => {
    const { clock, sink, source } = setup('click')
    source.play()
    clock.advance(0.7)
    source.pause()
    clock.advance(10)
    source.play()
    clock.advance(1.1)
    expectClose(sink.times(), [0, 0.5, 11, 11.5])
  })

  it('seek replanifica desde la nueva posición', () => {
    const { clock, sink, source } = setup('click')
    source.play()
    clock.advance(0.2)
    source.seek(4)
    expect(source.position()).toBeCloseTo(4)
    clock.advance(1.05)
    expectClose(sink.times(), [0, 0.2, 0.7, 1.2])
    expect(sink.triggers[1].voice).toBe('accent')
  })

  it('seek con la fuente en pausa no suena, acota y deja la posición', () => {
    const { clock, sink, source } = setup('click')
    source.seek(3)
    clock.advance(1)
    expect(sink.triggers).toHaveLength(0)
    expect(source.position()).toBeCloseTo(3)
    source.seek(999)
    expect(source.position()).toBeCloseTo(DURATION)
    source.seek(-5)
    expect(source.position()).toBe(0)
  })

  it('setRate en reproducción re-agenda con el nuevo tempo, sin duplicar', () => {
    const { clock, sink, source } = setup('click')
    source.play()
    clock.advance(0.7) // sonaron 0 y 0,5
    source.setRate(0.5)
    clock.advance(2.7)
    // el beat 1,0 está a 0,3 s de canción = 0,6 s reales: 0,7 + 0,6 = 1,3
    expectClose(sink.times(), [0, 0.5, 1.3, 2.3, 3.3])
  })

  it('el timer de planificación se limpia al pausar y al liberar', () => {
    const { clock, source } = setup('click')
    source.play()
    source.pause()
    expect(clock.activeTimers).toBe(0)
    source.play()
    source.dispose()
    expect(clock.activeTimers).toBe(0)
  })
})

describe('GeneratedBackingSource - loop A-B', () => {
  it('vuelve a A y re-agenda en el tiempo exacto', () => {
    const { clock, sink, source } = setup('click')
    source.setLoop({ startS: 1, endS: 2 })
    source.seek(1)
    source.play()
    clock.advance(3.05)
    expectClose(sink.times(), [0, 0.5, 1, 1.5, 2, 2.5, 3])
    expect(sink.times('accent')).toHaveLength(0) // 1,0 y 1,5 no son el 1 del compás
  })

  it('la posición queda dentro del loop', () => {
    const { clock, source } = setup('click')
    source.setLoop({ startS: 1, endS: 2 })
    source.seek(1.5)
    source.play()
    clock.advance(0.75)
    expect(source.position()).toBeCloseTo(1.25)
    for (let i = 0; i < 20; i++) {
      clock.advance(0.37)
      const p = source.position()
      expect(p).toBeGreaterThanOrEqual(1)
      expect(p).toBeLessThan(2)
    }
  })

  it('con velocidad 50 % el loop dura el doble en tiempo real', () => {
    const { clock, sink, source } = setup('click')
    source.setRate(0.5)
    source.setLoop({ startS: 0, endS: 1 })
    source.play()
    clock.advance(4.05)
    expectClose(sink.times(), [0, 1, 2, 3, 4])
  })

  it('un loop inválido lanza; uno que deja la posición afuera la lleva a A', () => {
    const { source } = setup('click')
    expect(() => source.setLoop({ startS: 2, endS: 1 })).toThrow(RangeError)
    expect(() => source.setLoop({ startS: 0, endS: 99 })).toThrow(RangeError)
    source.seek(5)
    source.setLoop({ startS: 1, endS: 2 })
    expect(source.position()).toBeCloseTo(1)
  })

  it('quitar el loop deja seguir hasta el final', () => {
    const { clock, source } = setup('click')
    const ended = vi.fn()
    source.onEnded(ended)
    source.setLoop({ startS: 0, endS: 1 })
    source.play()
    clock.advance(3)
    expect(ended).not.toHaveBeenCalled()
    source.setLoop(null)
    clock.advance(DURATION)
    expect(ended).toHaveBeenCalledTimes(1)
  })
})

describe('GeneratedBackingSource - final', () => {
  it('avisa onEnded al pasar el final y queda detenida en la duración', () => {
    const { clock, source } = setup('click')
    const ended = vi.fn()
    source.onEnded(ended)
    source.play()
    clock.advance(DURATION - 0.5)
    expect(ended).not.toHaveBeenCalled()
    clock.advance(1)
    expect(ended).toHaveBeenCalledTimes(1)
    expect(source.isPlaying()).toBe(false)
    expect(source.position()).toBeCloseTo(DURATION)
    clock.advance(5)
    expect(ended).toHaveBeenCalledTimes(1)
  })

  it('a 50 % tarda el doble en terminar', () => {
    const { clock, source } = setup('click')
    const ended = vi.fn()
    source.onEnded(ended)
    source.setRate(0.5)
    source.play()
    clock.advance(DURATION)
    expect(ended).not.toHaveBeenCalled()
    clock.advance(DURATION + 0.1)
    expect(ended).toHaveBeenCalledTimes(1)
  })

  it('play desde el final reinicia; el unsubscribe cancela el aviso', () => {
    const { clock, source } = setup('click')
    const ended = vi.fn()
    const off = source.onEnded(ended)
    source.seek(DURATION)
    source.play()
    expect(source.position()).toBe(0)
    off()
    clock.advance(DURATION + 1)
    expect(ended).not.toHaveBeenCalled()
  })

  it('la grilla alarga la duración si supera a las secciones', () => {
    const beats = Array.from({ length: 41 }, (_, i) => i * 0.5)
    const { source } = setup(
      'click',
      chart({ beat_grid: { beats_s: beats as [number, number, ...number[]] } }),
    )
    source.seek(15)
    expect(source.position()).toBeCloseTo(15)
  })
})
