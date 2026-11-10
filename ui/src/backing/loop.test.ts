import { describe, expect, it } from 'vitest'
import { isValidLoop, loopJumpTarget } from './loop'

describe('isValidLoop', () => {
  it('acepta A < B dentro de la duración', () => {
    expect(isValidLoop({ startS: 1, endS: 2 }, 10)).toBe(true)
    expect(isValidLoop({ startS: 0, endS: 10 }, 10)).toBe(true)
  })
  it('rechaza A >= B, negativos, B fuera de duración y no finitos', () => {
    expect(isValidLoop({ startS: 2, endS: 2 })).toBe(false)
    expect(isValidLoop({ startS: 3, endS: 2 })).toBe(false)
    expect(isValidLoop({ startS: -1, endS: 2 })).toBe(false)
    expect(isValidLoop({ startS: 1, endS: 11 }, 10)).toBe(false)
    expect(isValidLoop({ startS: 1, endS: Number.NaN })).toBe(false)
  })
  it('sin duración conocida (NaN) no limita B', () => {
    expect(isValidLoop({ startS: 1, endS: 99 }, Number.NaN)).toBe(true)
  })
})

describe('loopJumpTarget', () => {
  const loop = { startS: 2, endS: 5 }
  it('salta a A al llegar o pasar B', () => {
    expect(loopJumpTarget(5, loop)).toBe(2)
    expect(loopJumpTarget(5.2, loop)).toBe(2)
  })
  it('no salta antes de B ni sin loop', () => {
    expect(loopJumpTarget(4.9, loop)).toBeNull()
    expect(loopJumpTarget(99, null)).toBeNull()
  })
})
