import { describe, expect, it } from 'vitest'
import type { ChartChord, ChartSection, SongChartContent } from '../songs/types'
import { generateArrangement, parseChordName, shapeMidi } from './arrangement'

const SHAPE_C: ChartChord['shape'] = ['x', 3, 2, 0, 1, 0]
const SHAPE_NONE: ChartChord['shape'] = ['x', 'x', 'x', 'x', 'x', 'x']

const chord = (t_s: number, name: string, shape = SHAPE_NONE): ChartChord => ({
  t_s,
  name,
  shape,
  confidence: 0.9,
})

const section = (
  chords: ChartChord[],
  end_s = 4,
  start_s = 0,
): ChartSection => ({
  id: 'a',
  name: 'A',
  start_s,
  end_s,
  order: 0,
  chord_source: 'user',
  chords,
})

/** BPM 120: un beat cada 0.5 s. */
const chart = (over: Partial<SongChartContent> = {}): SongChartContent => ({
  instrument: 'classical',
  bpm: 120,
  time_signature: '4/4',
  sections: [section([])],
  ...over,
})

const grid = (n: number, downbeats?: number[]) => ({
  beats_s: Array.from({ length: n }, (_, i) => i * 0.5) as [
    number,
    number,
    ...number[],
  ],
  downbeats_s: downbeats,
})

type Events = ReturnType<typeof generateArrangement>
const voice = (events: Events, v: string) => events.filter((e) => e.voice === v)
const beatsOf = (events: Events, v: string) =>
  voice(events, v).map((e) => e.beat)

describe('batería', () => {
  it('4/4: bombo en 1 y 3, redoblante en 2 y 4, hi-hat en corcheas', () => {
    const firstBar = generateArrangement(chart({ beat_grid: grid(9) })).filter(
      (e) => e.beat < 4,
    )
    expect(beatsOf(firstBar, 'kick')).toEqual([0, 2])
    expect(beatsOf(firstBar, 'snare')).toEqual([1, 3])
    expect(beatsOf(firstBar, 'hihat')).toEqual([0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5])
  })

  it('3/4 tiene un solo bombo y dos redoblantes por compás', () => {
    const events = generateArrangement(
      chart({ time_signature: '3/4', beat_grid: grid(7) }),
    ).filter((e) => e.beat < 3)
    expect(beatsOf(events, 'kick')).toEqual([0])
    expect(beatsOf(events, 'snare')).toEqual([1, 2])
  })

  it('6/8 dura 2 beats por compás con hi-hat en seis corcheas', () => {
    const events = generateArrangement(
      chart({ time_signature: '6/8', beat_grid: grid(9) }),
    )
    expect(beatsOf(events, 'kick').slice(0, 3)).toEqual([0, 2, 4])
    const hats = voice(events, 'hihat').filter((e) => e.beat < 2)
    expect(hats).toHaveLength(6)
    expect(hats[1].beat).toBeCloseTo(1 / 3)
  })

  it('un compás desconocido cae a 4/4', () => {
    const odd = generateArrangement(
      chart({ time_signature: '7/8', beat_grid: grid(9) }),
    )
    expect(odd).toEqual(generateArrangement(chart({ beat_grid: grid(9) })))
  })

  it('el primer tiempo de cada compás sale de downbeats_s', () => {
    // Anacrusa: el compás arranca en el beat 1 (0.5 s).
    const events = generateArrangement(
      chart({ beat_grid: grid(9, [0.5, 2.5]) }),
    )
    expect(beatsOf(events, 'kick').slice(0, 3)).toEqual([1, 3, 5])
    expect(beatsOf(events, 'kick')).not.toContain(0)
  })

  it('una sección sin acordes sólo tiene batería', () => {
    const events = generateArrangement(chart({ beat_grid: grid(9) }))
    expect(events.length).toBeGreaterThan(0)
    expect(
      events.every((e) => ['kick', 'snare', 'hihat'].includes(e.voice)),
    ).toBe(true)
  })

  it('no suena batería fuera de las secciones', () => {
    const events = generateArrangement(
      chart({ beat_grid: grid(17), sections: [section([], 4, 2)] }),
    )
    expect(Math.min(...events.map((e) => e.beat))).toBeGreaterThanOrEqual(4)
    expect(Math.max(...events.map((e) => e.beat))).toBeLessThan(8)
  })
})

describe('bajo y acordes', () => {
  it('el bajo toca la fundamental en octava 2-3 y el acorde, las notas de la forma', () => {
    const events = generateArrangement(
      chart({
        beat_grid: grid(9),
        sections: [section([chord(0, 'C', SHAPE_C)])],
      }),
    )
    expect(voice(events, 'bass')[0].midi).toBe(36)
    expect(voice(events, 'chord')[0]).toMatchObject({
      beat: 0,
      midi: [48, 52, 55, 60, 64],
    })
  })

  it('el bajo de un acorde con bajo alterado es esa nota (C/G -> G)', () => {
    const events = generateArrangement(
      chart({ beat_grid: grid(9), sections: [section([chord(0, 'C/G')])] }),
    )
    expect(voice(events, 'bass')[0].midi).toBe(43)
  })

  it('sin forma arma la triada desde el nombre', () => {
    const events = generateArrangement(
      chart({ beat_grid: grid(9), sections: [section([chord(0, 'Am')])] }),
    )
    expect(voice(events, 'chord')[0].midi).toEqual([57, 60, 64])
  })

  it('un acorde que cambia a mitad de compás corta al anterior', () => {
    const events = generateArrangement(
      chart({
        beat_grid: grid(9),
        sections: [section([chord(0, 'C'), chord(1, 'G')], 2)],
      }),
    )
    const chords = voice(events, 'chord')
    expect(chords[0]).toMatchObject({ beat: 0, durBeats: 2 })
    expect(chords[1]).toMatchObject({
      beat: 2,
      durBeats: 2,
      midi: [55, 59, 62],
    })
    expect(voice(events, 'bass').map((e) => [e.beat, e.midi])).toEqual([
      [0, 36],
      [2, 43],
    ])
  })

  it('un acorde largo se vuelve a tocar en cada compás', () => {
    const events = generateArrangement(
      chart({ beat_grid: grid(9), sections: [section([chord(0, 'C')])] }),
    )
    expect(beatsOf(events, 'chord')).toEqual([0, 4])
    expect(beatsOf(events, 'bass')).toEqual([0, 4])
  })

  it('N.C. no tiene bajo ni acordes y corta el acorde anterior', () => {
    const events = generateArrangement(
      chart({
        beat_grid: grid(9),
        sections: [section([chord(0, 'C'), chord(1, 'N.C.')])],
      }),
    )
    expect(voice(events, 'chord')).toHaveLength(1)
    expect(voice(events, 'chord')[0].durBeats).toBe(2)
    expect(voice(events, 'bass')).toHaveLength(1)
  })
})

describe('sin beat_grid', () => {
  it('usa BPM constante desde 0', () => {
    const events = generateArrangement(
      chart({ bpm: 60, sections: [section([chord(2, 'C')], 4)] }),
    )
    // 60 BPM: un beat por segundo.
    expect(voice(events, 'chord')[0]).toMatchObject({ beat: 2, durBeats: 2 })
    expect(beatsOf(events, 'kick')).toEqual([0, 2])
  })
})

describe('capo y grilla degenerada', () => {
  it('suma el capo a las notas de la forma (Bm con capo 2 y forma de Am)', () => {
    const shapeAm: ChartChord['shape'] = ['x', 0, 2, 2, 1, 0]
    const events = generateArrangement(
      chart({
        capo: 2,
        beat_grid: grid(9),
        sections: [section([chord(0, 'Bm', shapeAm)])],
      }),
    )
    expect(voice(events, 'chord')[0].midi).toEqual([47, 54, 59, 62, 66])
    expect(voice(events, 'bass')[0].midi).toBe(47)
  })

  it('con beats_s de menos de 2 elementos usa BPM constante', () => {
    const events = generateArrangement(
      chart({ bpm: 60, beat_grid: { beats_s: [0] } as never }),
    )
    expect(beatsOf(events, 'kick')).toEqual([0, 2])
  })
})

describe('rango y orden', () => {
  it('filtra por rango de beats (inicio inclusivo, fin exclusivo)', () => {
    const events = generateArrangement(chart({ beat_grid: grid(17) }), {
      fromBeat: 4,
      toBeat: 8,
    })
    expect(events.every((e) => e.beat >= 4 && e.beat < 8)).toBe(true)
    expect(beatsOf(events, 'kick')).toEqual([4, 6])
  })

  it('devuelve los eventos ordenados por tiempo', () => {
    const events = generateArrangement(
      chart({
        beat_grid: grid(9),
        sections: [section([chord(0, 'C'), chord(1, 'G')])],
      }),
    )
    const beats = events.map((e) => e.beat)
    expect(beats).toEqual([...beats].sort((a, b) => a - b))
  })
})

describe('helpers', () => {
  it.each([
    ['C', 0, 0, [0, 4, 7]],
    ['F#m7', 6, 6, [0, 3, 7]],
    ['Bb', 10, 10, [0, 4, 7]],
    ['Bdim', 11, 11, [0, 3, 6]],
    ['Dsus4', 2, 2, [0, 5, 7]],
    ['Cmaj7', 0, 0, [0, 4, 7]],
    ['C/G', 0, 7, [0, 4, 7]],
  ])('parseChordName(%s)', (name, root, bass, intervals) => {
    expect(parseChordName(name)).toEqual({ root, bass, intervals })
  })

  it('parseChordName devuelve null para N.C. y nombres raros', () => {
    expect(parseChordName('N.C.')).toBeNull()
    expect(parseChordName('NC')).toBeNull()
    expect(parseChordName('???')).toBeNull()
  })

  it('shapeMidi omite las cuerdas mudas', () => {
    expect(shapeMidi(['x', 'x', 0, 2, 3, 2])).toEqual([50, 57, 62, 66])
  })
})
