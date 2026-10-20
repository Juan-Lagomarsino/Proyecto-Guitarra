import { noteAt, pitchClass, sameNote, STANDARD_TUNING } from './pitch'

describe('pitchClass', () => {
  it('resuelve naturales, sostenidos y bemoles', () => {
    expect(pitchClass('C')).toBe(0)
    expect(pitchClass('A#')).toBe(10)
    expect(pitchClass('Bb')).toBe(10)
    expect(pitchClass('E2')).toBe(4)
  })

  it('maneja los bordes B#, Cb, E# y Fb', () => {
    expect(pitchClass('B#')).toBe(0)
    expect(pitchClass('Cb')).toBe(11)
    expect(pitchClass('E#')).toBe(5)
    expect(pitchClass('Fb')).toBe(4)
  })

  it('rechaza notas inválidas', () => {
    expect(() => pitchClass('H')).toThrow()
  })
})

describe('noteAt', () => {
  it('la cuerda al aire es la afinación (6 = grave, 1 = aguda)', () => {
    expect(noteAt(STANDARD_TUNING, 6, 0)).toBe(4)
    expect(noteAt(STANDARD_TUNING, 5, 0)).toBe(9)
    expect(noteAt(STANDARD_TUNING, 1, 0)).toBe(4)
  })

  it('suma semitonos por traste y da la vuelta a la octava', () => {
    expect(noteAt(STANDARD_TUNING, 6, 5)).toBe(9)
    expect(noteAt(STANDARD_TUNING, 1, 12)).toBe(4)
    expect(noteAt(STANDARD_TUNING, 2, 1)).toBe(0)
  })

  it('respeta afinaciones alternativas', () => {
    expect(noteAt(['D2', 'A2', 'D3', 'G3', 'B3', 'E4'], 6, 0)).toBe(2)
  })

  it('no devuelve negativos con trastes negativos', () => {
    expect(noteAt(STANDARD_TUNING, 6, -5)).toBe(11)
    expect(noteAt(STANDARD_TUNING, 6, -12)).toBe(4)
  })

  it('rechaza cuerdas fuera de 1 a 6', () => {
    expect(() => noteAt(STANDARD_TUNING, 0, 0)).toThrow()
    expect(() => noteAt(STANDARD_TUNING, 7, 0)).toThrow()
  })
})

describe('sameNote', () => {
  it('una nota inválida no coincide con nada', () => {
    expect(sameNote(10, 'xyz')).toBe(false)
    expect(sameNote(10, '')).toBe(false)
  })

  it('compara enarmónicos', () => {
    expect(sameNote(10, 'Bb')).toBe(true)
    expect(sameNote(10, 'A#')).toBe(true)
    expect(sameNote(10, 'B')).toBe(false)
  })
})
