import { render, screen } from '@testing-library/react'
import type { Notation } from '../../notation/types'
import { Fretboard } from './Fretboard'

const notation = (over: Partial<Notation> = {}): Notation => ({
  bpm: 60,
  tonic: 'A',
  events: [
    { t: 0, dur: 1, string: 6, fret: 5 }, // A (tónica)
    { t: 1, dur: 1, string: 5, fret: 7 }, // E
    { t: 2, dur: 1, string: 6, fret: 5 }, // repetida
  ],
  ...over,
})

const notes = (container: HTMLElement) => [
  ...container.querySelectorAll('[data-testid="note"]'),
]
const at = (container: HTMLElement, string: number, fret: number) =>
  notes(container).find(
    (n) =>
      n.getAttribute('data-string') === String(string) &&
      n.getAttribute('data-fret') === String(fret),
  )!

describe('Fretboard', () => {
  it('es una imagen accesible con etiqueta en español', () => {
    render(<Fretboard notation={notation()} activeIndex={null} />)
    expect(screen.getByRole('img', { name: /mástil/i })).toBeInTheDocument()
  })

  it('dibuja una sola vez cada posición distinta', () => {
    const { container } = render(
      <Fretboard notation={notation()} activeIndex={null} />,
    )
    expect(notes(container)).toHaveLength(2)
  })

  it('ubica la nota: cuerda 1 arriba, cuerda 6 abajo, traste hacia la derecha', () => {
    const { container } = render(
      <Fretboard
        notation={notation({
          events: [
            { t: 0, dur: 1, string: 1, fret: 3 },
            { t: 1, dur: 1, string: 6, fret: 3 },
            { t: 2, dur: 1, string: 6, fret: 5 },
          ],
        })}
        activeIndex={null}
        fretRange={[2, 10]}
      />,
    )
    const top = at(container, 1, 3)
    const bottom = at(container, 6, 3)
    const right = at(container, 6, 5)
    expect(Number(top.getAttribute('cy'))).toBeLessThan(
      Number(bottom.getAttribute('cy')),
    )
    expect(top.getAttribute('cx')).toBe(bottom.getAttribute('cx'))
    expect(Number(right.getAttribute('cx'))).toBeGreaterThan(
      Number(bottom.getAttribute('cx')),
    )
  })

  it('marca tónica, otra y suena ahora', () => {
    const { container } = render(
      <Fretboard notation={notation()} activeIndex={1} />,
    )
    expect(at(container, 6, 5)).toHaveAttribute('data-state', 'tonic')
    expect(at(container, 5, 7)).toHaveAttribute('data-state', 'active')
  })

  it('el estado "otra" es el del resto', () => {
    const { container } = render(
      <Fretboard notation={notation()} activeIndex={0} />,
    )
    expect(at(container, 5, 7)).toHaveAttribute('data-state', 'other')
  })

  it('suena ahora tiene prioridad sobre tónica', () => {
    const { container } = render(
      <Fretboard notation={notation()} activeIndex={0} />,
    )
    expect(at(container, 6, 5)).toHaveAttribute('data-state', 'active')
  })

  it('resuelve enarmónicos al comparar con la tónica', () => {
    const { container } = render(
      <Fretboard
        notation={notation({
          tonic: 'Bb',
          events: [{ t: 0, dur: 1, string: 5, fret: 1 }], // A#
        })}
        activeIndex={null}
      />,
    )
    expect(at(container, 5, 1)).toHaveAttribute('data-state', 'tonic')
  })

  it('sin tónica todo es "otra"', () => {
    const { container } = render(
      <Fretboard notation={notation({ tonic: null })} activeIndex={null} />,
    )
    expect(
      notes(container).every((n) => n.getAttribute('data-state') === 'other'),
    ).toBe(true)
  })

  it('una tónica inválida se trata como sin tónica y no rompe el render', () => {
    const { container } = render(
      <Fretboard notation={notation({ tonic: 'H#' })} activeIndex={null} />,
    )
    expect(
      notes(container).every((n) => n.getAttribute('data-state') === 'other'),
    ).toBe(true)
  })

  it('el rango por props define los números de traste', () => {
    render(
      <Fretboard notation={notation()} activeIndex={null} fretRange={[3, 6]} />,
    )
    const labels = screen
      .getAllByTestId('fret-number')
      .map((t) => t.textContent)
    expect(labels).toEqual(['3', '4', '5', '6'])
  })

  it('sin fretRange lo calcula de los eventos', () => {
    render(<Fretboard notation={notation()} activeIndex={null} />)
    const labels = screen
      .getAllByTestId('fret-number')
      .map((t) => t.textContent)
    expect(labels[0]).toBe('4')
    expect(labels).toHaveLength(9)
  })

  it('dibuja incrustaciones: simples en 3/5/7/9 y doble en 12', () => {
    const { container } = render(
      <Fretboard
        notation={notation()}
        activeIndex={null}
        fretRange={[0, 12]}
      />,
    )
    expect(container.querySelectorAll('[data-inlay="3"]')).toHaveLength(1)
    expect(container.querySelectorAll('[data-inlay="12"]')).toHaveLength(2)
    expect(container.querySelectorAll('[data-inlay="4"]')).toHaveLength(0)
  })

  it('nombra las cuerdas e B G D A E de arriba a abajo', () => {
    render(<Fretboard notation={notation()} activeIndex={null} />)
    const names = screen.getAllByTestId('string-name').map((t) => t.textContent)
    expect(names).toEqual(['e', 'B', 'G', 'D', 'A', 'E'])
  })

  it('muestra la leyenda salvo que se oculte', () => {
    const { rerender } = render(
      <Fretboard notation={notation()} activeIndex={null} />,
    )
    expect(screen.getByText('Tónica')).toBeInTheDocument()
    expect(screen.getByText('Otras notas')).toBeInTheDocument()
    expect(screen.getByText('Suena ahora')).toBeInTheDocument()
    rerender(
      <Fretboard notation={notation()} activeIndex={null} showLegend={false} />,
    )
    expect(screen.queryByText('Tónica')).not.toBeInTheDocument()
  })

  it('usa la afinación de la notación', () => {
    const { container } = render(
      <Fretboard
        notation={notation({
          tonic: 'D',
          tuning: ['D2', 'A2', 'D3', 'G3', 'B3', 'E4'],
          events: [{ t: 0, dur: 1, string: 6, fret: 0 }],
        })}
        activeIndex={null}
      />,
    )
    expect(at(container, 6, 0)).toHaveAttribute('data-state', 'tonic')
  })
})
