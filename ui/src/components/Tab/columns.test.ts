import type { NoteEvent } from '../../notation/types'
import { beatsPerBar, buildColumns, columnWidth, stringName } from './columns'

const ev = (
  t: number,
  string: number,
  fret: number,
  extra: Partial<NoteEvent> = {},
): NoteEvent => ({ t, dur: 1, string, fret, ...extra })

describe('buildColumns', () => {
  it('devuelve vacío sin eventos', () => {
    expect(buildColumns([], 4)).toEqual([])
  })

  it('agrupa eventos simultáneos en una columna y conserva el índice original', () => {
    const cols = buildColumns([ev(0, 6, 0), ev(0, 5, 2), ev(1, 6, 3)], 4)
    expect(cols).toHaveLength(2)
    expect(cols[0].notes.map((n) => n.index)).toEqual([0, 1])
    expect(cols[1].notes[0].index).toBe(2)
  })

  it('ordena por tiempo aunque lleguen desordenados', () => {
    const cols = buildColumns([ev(2, 1, 5), ev(0, 1, 3)], 4)
    expect(cols.map((c) => c.t)).toEqual([0, 2])
    expect(cols[0].notes[0].index).toBe(1)
  })

  it('calcula el compás de cada columna', () => {
    const cols = buildColumns(
      [ev(0, 1, 0), ev(3.5, 1, 0), ev(4, 1, 0), ev(9, 1, 0)],
      4,
    )
    expect(cols.map((c) => c.bar)).toEqual([0, 0, 1, 2])
  })

  it('usa la mayor duración de la columna', () => {
    const cols = buildColumns(
      [ev(0, 1, 0, { dur: 0.5 }), ev(0, 2, 0, { dur: 2 })],
      4,
    )
    expect(cols[0].dur).toBe(2)
  })

  it('arma las anotaciones de técnica, sin duplicar y con el bend', () => {
    const cols = buildColumns(
      [
        ev(0, 1, 5),
        ev(0, 2, 5),
        ev(1, 1, 7, { technique: 'b', bend: 1 }),
        ev(2, 1, 7, { technique: 'b', bend: 0.5 }),
        ev(3, 1, 7, { technique: 'pm' }),
        ev(4, 1, 7, { technique: null }),
      ],
      4,
    )
    expect(cols[1].annotations).toEqual([{ text: 'b1', placement: 'on' }])
    expect(cols[2].annotations).toEqual([{ text: 'b½', placement: 'on' }])
    expect(cols[3].annotations).toEqual([{ text: 'PM', placement: 'on' }])
    expect(cols[4].annotations).toEqual([])
  })

  it('muestra x en lugar del traste para notas muertas', () => {
    const cols = buildColumns([ev(0, 3, 0, { technique: 'x' })], 4)
    expect(cols[0].notes[0].label).toBe('x')
    expect(cols[0].annotations).toEqual([])
  })

  it('las notas llevan el traste como etiqueta', () => {
    expect(buildColumns([ev(0, 3, 12)], 4)[0].notes[0].label).toBe('12')
  })
})

describe('técnicas de dos notas', () => {
  it('ejemplo del plan: la h va entre el 5 y el 7, anotada en el destino', () => {
    const cols = buildColumns(
      [
        ev(0, 6, 5, { dur: 0.5 }),
        ev(0.5, 6, 7, { dur: 0.5, technique: 'h' }),
        ev(1, 5, 7, { technique: 'b', bend: 1 }),
      ],
      4,
    )
    expect(cols[0].annotations).toEqual([])
    expect(cols[1].annotations).toEqual([
      { text: 'h', placement: 'between', fromT: 0 },
    ])
  })

  it('el origen es el evento anterior en la misma cuerda', () => {
    const cols = buildColumns(
      [ev(0, 6, 5), ev(1, 5, 2), ev(2, 6, 7, { technique: 'p' })],
      4,
    )
    expect(cols[2].annotations).toEqual([
      { text: 'p', placement: 'between', fromT: 0 },
    ])
  })

  it('sin evento previo en la cuerda usa la columna anterior', () => {
    const cols = buildColumns([ev(0, 6, 5), ev(1, 5, 7, { technique: '/' })], 4)
    expect(cols[1].annotations).toEqual([
      { text: '/', placement: 'between', fromT: 0 },
    ])
  })

  it('en el primer evento no hay marca de unión: queda como etiqueta', () => {
    const cols = buildColumns([ev(0, 6, 7, { technique: 'h' })], 4)
    expect(cols[0].annotations).toEqual([{ text: 'h', placement: 'on' }])
  })
})

describe('tiempos en punto flotante', () => {
  it('0.1 + 0.2 y 0.3 caen en la misma columna', () => {
    const cols = buildColumns([ev(0.1 + 0.2, 6, 0), ev(0.3, 5, 2)], 4)
    expect(cols).toHaveLength(1)
    expect(cols[0].notes).toHaveLength(2)
  })

  it('el compás no se corre por error de redondeo', () => {
    const cols = buildColumns([ev(4 - 1e-12, 6, 0)], 4)
    expect(cols[0].bar).toBe(1)
  })
})

describe('beatsPerBar', () => {
  it.each([
    ['4/4', 4],
    ['3/4', 3],
    ['6/8', 3],
    ['12/8', 6],
    [undefined, 4],
    ['basura', 4],
    ['0/4', 4],
  ])('%s -> %s', (sig, expected) => {
    expect(beatsPerBar(sig)).toBe(expected)
  })
})

describe('columnWidth', () => {
  it('crece con la duración y tiene tope y piso', () => {
    expect(columnWidth(0.25)).toBe(26)
    expect(columnWidth(1)).toBe(26)
    expect(columnWidth(2)).toBeGreaterThan(columnWidth(1))
    expect(columnWidth(100)).toBe(72)
  })
})

describe('stringName', () => {
  const tuning: [string, string, string, string, string, string] = [
    'E2',
    'A2',
    'D3',
    'G3',
    'B3',
    'E4',
  ]
  it('quita la octava y baja a minúscula la cuerda 1', () => {
    expect([1, 2, 3, 4, 5, 6].map((s) => stringName(tuning, s))).toEqual([
      'e',
      'B',
      'G',
      'D',
      'A',
      'E',
    ])
  })
  it('respeta afinaciones alteradas', () => {
    const drop: typeof tuning = ['D2', 'A2', 'D3', 'G3', 'B3', 'E4']
    expect(stringName(drop, 6)).toBe('D')
  })
})
