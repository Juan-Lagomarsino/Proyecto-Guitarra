import type { NoteEvent } from '../../notation/types'
import { collectPositions, computeFretRange } from './layout'

const ev = (string: number, fret: number): NoteEvent => ({
  t: 0,
  dur: 1,
  string,
  fret,
})

describe('computeFretRange', () => {
  it('agrega un traste de margen y garantiza 9 trastes de ancho', () => {
    expect(computeFretRange([ev(1, 5), ev(2, 7)])).toEqual([4, 12])
  })

  it('amplía hacia arriba si los eventos son más anchos', () => {
    expect(computeFretRange([ev(1, 2), ev(2, 15)])).toEqual([1, 16])
  })

  it('no baja de 0', () => {
    expect(computeFretRange([ev(1, 0), ev(2, 2)])).toEqual([0, 8])
  })

  it('sin eventos usa 0 a 8', () => {
    expect(computeFretRange([])).toEqual([0, 8])
  })
})

describe('collectPositions', () => {
  it('deduplica posiciones conservando el orden', () => {
    expect(collectPositions([ev(1, 3), ev(2, 5), ev(1, 3)])).toEqual([
      { string: 1, fret: 3 },
      { string: 2, fret: 5 },
    ])
  })
})
