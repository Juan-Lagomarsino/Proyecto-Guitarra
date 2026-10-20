import type { TabColumn } from './columns'
import { partitionSystems } from './systems'

const col = (bar: number, t: number, width = 30): TabColumn => ({
  t,
  dur: 1,
  bar,
  width,
  notes: [],
  annotations: [],
})

describe('partitionSystems', () => {
  it('devuelve vacío sin columnas', () => {
    expect(partitionSystems([], 500)).toEqual([])
  })

  it('deja todo en un sistema si entra', () => {
    const cols = [col(0, 0), col(0, 1), col(1, 2)]
    expect(partitionSystems(cols, 500)).toEqual([cols])
  })

  it('no parte un compás si puede evitarlo', () => {
    const cols = [
      col(0, 0),
      col(0, 1),
      col(0, 2),
      col(1, 3),
      col(1, 4),
      col(1, 5),
    ]
    // cada compás mide 90; el ancho útil alcanza para uno y no para dos
    const systems = partitionSystems(cols, 150)
    expect(systems.map((s) => s.map((c) => c.bar))).toEqual([
      [0, 0, 0],
      [1, 1, 1],
    ])
  })

  it('junta varios compases enteros mientras entren', () => {
    const cols = [col(0, 0), col(1, 4), col(2, 8), col(3, 12)]
    const systems = partitionSystems(cols, 70)
    expect(systems.map((s) => s.length)).toEqual([2, 2])
  })

  it('parte por columna un compás que no entra solo', () => {
    const cols = [col(0, 0), col(0, 1), col(0, 2), col(0, 3), col(0, 4)]
    const systems = partitionSystems(cols, 70)
    expect(systems.map((s) => s.length)).toEqual([2, 2, 1])
  })

  it('un compás que no entra solo arranca en un sistema nuevo', () => {
    const cols = [col(0, 0), col(1, 4), col(1, 5), col(1, 6), col(1, 7)]
    const systems = partitionSystems(cols, 100)
    expect(systems[0].map((c) => c.bar)).toEqual([0])
    expect(systems.flat()).toHaveLength(5)
  })

  it('siempre pone al menos una columna por sistema aunque no entre', () => {
    const systems = partitionSystems([col(0, 0, 500), col(0, 1, 500)], 100)
    expect(systems.map((s) => s.length)).toEqual([1, 1])
  })

  it('no pierde ni reordena columnas', () => {
    const cols = Array.from({ length: 23 }, (_, i) => col(Math.floor(i / 4), i))
    expect(partitionSystems(cols, 200).flat()).toEqual(cols)
  })
})
