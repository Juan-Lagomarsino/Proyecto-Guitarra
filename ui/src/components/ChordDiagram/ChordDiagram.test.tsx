import { render, screen } from '@testing-library/react'
import type { ChartChord } from '../../songs/types'
import { ChordDiagram, computeWindow } from './ChordDiagram'

type Chord = Pick<ChartChord, 'name' | 'shape' | 'barre'>

const C: Chord = { name: 'C', shape: ['x', 3, 2, 0, 1, 0] }
const AM: Chord = { name: 'Am', shape: ['x', 0, 2, 2, 1, 0] }
const F: Chord = {
  name: 'F',
  shape: [1, 3, 3, 2, 1, 1],
  barre: { fret: 1, from_string: 6, to_string: 1 },
}
const BM: Chord = {
  name: 'Bm',
  shape: ['x', 2, 4, 4, 3, 2],
  barre: { fret: 2, from_string: 5, to_string: 1 },
}
const A_BARRE: Chord = {
  name: 'A',
  shape: [5, 7, 7, 6, 5, 5],
  barre: { fret: 5, from_string: 6, to_string: 1 },
}
const E5: Chord = { name: 'E5', shape: [0, 2, 2, 'x', 'x', 'x'] }
const A5: Chord = { name: 'A5', shape: ['x', 0, 2, 2, 'x', 'x'] }
const OPEN: Chord = { name: 'Em', shape: [0, 0, 0, 0, 0, 0] }

const q = (c: HTMLElement, sel: string) => [...c.querySelectorAll(sel)]
const dots = (c: HTMLElement) => q(c, '[data-testid="dot"]')
const markers = (c: HTMLElement) =>
  q(c, '[data-testid="string-marker"]').map((m) => m.textContent)

describe('ChordDiagram', () => {
  it('dibuja un acorde abierto: 6 cuerdas, cejuela, nombre y marcadores (C)', () => {
    const { container } = render(<ChordDiagram chord={C} />)
    expect(q(container, '[data-testid="string"]')).toHaveLength(6)
    expect(q(container, '[data-testid="nut"]')).toHaveLength(1)
    expect(screen.getByText('C')).toBeInTheDocument()
    expect(dots(container)).toHaveLength(3)
    expect(markers(container)).toEqual(['x', '', '', 'o', '', 'o'])
    expect(q(container, '[data-testid="start-fret"]')).toHaveLength(0)
  })

  it('dibuja Am abierto con 3 puntos', () => {
    const { container } = render(<ChordDiagram chord={AM} />)
    expect(dots(container)).toHaveLength(3)
    expect(markers(container)).toEqual(['x', 'o', '', '', '', 'o'])
  })

  it('dibuja la cejilla en el traste 1 sobre todas las cuerdas (F)', () => {
    const { container } = render(<ChordDiagram chord={F} />)
    expect(q(container, '[data-testid="barre"]')).toHaveLength(1)
    expect(q(container, '[data-testid="nut"]')).toHaveLength(1)
    // los puntos del traste de la cejilla quedan cubiertos por ella
    expect(dots(container)).toHaveLength(3)
  })

  it('cejilla alta sin cejuela y con traste inicial (A en el 5)', () => {
    const { container } = render(<ChordDiagram chord={A_BARRE} />)
    expect(q(container, '[data-testid="nut"]')).toHaveLength(0)
    expect(screen.getByTestId('start-fret')).toHaveTextContent('5fr')
    expect(q(container, '[data-testid="barre"]')).toHaveLength(1)
  })

  it('cejilla en el 2 conserva la cejuela (Bm) y abarca de la cuerda 5 a la 1', () => {
    const { container } = render(<ChordDiagram chord={BM} />)
    expect(q(container, '[data-testid="nut"]')).toHaveLength(1)
    expect(q(container, '[data-testid="start-fret"]')).toHaveLength(0)
    const barre = q(container, '[data-testid="barre"]')[0]
    const stringXs = q(container, '[data-testid="string"]').map((s) =>
      Number(s.getAttribute('x1')),
    )
    expect(Number(barre.getAttribute('data-from-x'))).toBe(stringXs[1])
    expect(Number(barre.getAttribute('data-to-x'))).toBe(stringXs[5])
  })

  it('power chords marcan las cuerdas muteadas (E5, A5)', () => {
    const e5 = render(<ChordDiagram chord={E5} />)
    expect(markers(e5.container)).toEqual(['o', '', '', 'x', 'x', 'x'])
    expect(dots(e5.container)).toHaveLength(2)
    const a5 = render(<ChordDiagram chord={A5} />)
    expect(markers(a5.container)).toEqual(['x', 'o', '', '', 'x', 'x'])
  })

  it('todas al aire: seis "o" y ningún punto', () => {
    const { container } = render(<ChordDiagram chord={OPEN} />)
    expect(markers(container)).toEqual(['o', 'o', 'o', 'o', 'o', 'o'])
    expect(dots(container)).toHaveLength(0)
  })

  it('es una imagen accesible con descripción del acorde', () => {
    render(<ChordDiagram chord={A_BARRE} />)
    const label = screen.getByRole('img').getAttribute('aria-label')!
    expect(label).toMatch(/acorde A/i)
    expect(label).toMatch(/cejilla en el traste 5/i)
    expect(label).toMatch(/cuerda 6 traste 5/i)
  })

  it('el aria-label menciona cuerdas al aire y muteadas', () => {
    render(<ChordDiagram chord={E5} />)
    const label = screen.getByRole('img').getAttribute('aria-label')!
    expect(label).toMatch(/cuerda 6 al aire/i)
    expect(label).toMatch(/cuerda 3 muteada/i)
  })

  it('resalta la tónica calculada desde la forma', () => {
    const { container } = render(<ChordDiagram chord={C} tonic="C" />)
    const tonics = dots(container).filter(
      (d) => d.getAttribute('data-tonic') === 'true',
    )
    // C: cuerda 5 traste 3 y cuerda 2 traste 1
    expect(tonics.map((d) => d.getAttribute('data-string')).sort()).toEqual([
      '2',
      '5',
    ])
  })

  it('sin tónica no resalta nada', () => {
    const { container } = render(<ChordDiagram chord={C} />)
    expect(
      dots(container).filter((d) => d.getAttribute('data-tonic') === 'true'),
    ).toHaveLength(0)
  })

  it('muestra la digitación dentro de los puntos', () => {
    render(<ChordDiagram chord={C} fingers={[null, 3, 2, null, 1, null]} />)
    expect(screen.getAllByTestId('finger').map((f) => f.textContent)).toEqual([
      '3',
      '2',
      '1',
    ])
  })

  it('dibuja la tónica sobre la cejilla sin duplicar puntos (F)', () => {
    const { container } = render(<ChordDiagram chord={F} tonic="F" />)
    const tonics = dots(container).filter(
      (d) => d.getAttribute('data-tonic') === 'true',
    )
    // F: cuerda 6 (bajo la cejilla), cuerda 4 (traste 3) y cuerda 1 (bajo la cejilla)
    expect(tonics.map((d) => d.getAttribute('data-string')).sort()).toEqual([
      '1',
      '4',
      '6',
    ])
    const strings = dots(container).map((d) => d.getAttribute('data-string'))
    expect(new Set(strings).size).toBe(strings.length)
  })

  it('dibuja la tónica sobre la cejilla de Bm en el 2', () => {
    const { container } = render(<ChordDiagram chord={BM} tonic="B" />)
    const strings = dots(container)
      .filter((d) => d.getAttribute('data-tonic') === 'true')
      .map((d) => d.getAttribute('data-string'))
    expect(strings).toContain('5')
  })

  it('con cejilla del 1 al 5 muestra cejuela y no "1fr"', () => {
    const chord: Chord = {
      name: 'X',
      shape: [1, 3, 5, 3, 1, 1],
      barre: { fret: 1, from_string: 6, to_string: 1 },
    }
    expect(computeWindow(chord)).toEqual({ start: 1, rows: 5, hasNut: true })
    const { container } = render(<ChordDiagram chord={chord} />)
    expect(q(container, '[data-testid="nut"]')).toHaveLength(1)
    expect(q(container, '[data-testid="start-fret"]')).toHaveLength(0)
  })

  it('marca con color de tónica la "o" de una cuerda al aire tónica', () => {
    const { container } = render(<ChordDiagram chord={AM} tonic="A" />)
    const open = q(container, '[data-testid="string-marker"]').filter((m) =>
      m.classList.contains('chord-diagram__marker--tonic'),
    )
    expect(open).toHaveLength(1)
    expect(open[0]).toHaveTextContent('o')
  })

  it('respeta size en el ancho del SVG', () => {
    render(<ChordDiagram chord={C} size={200} />)
    expect(screen.getByRole('img')).toHaveAttribute('width', '200')
  })
})
