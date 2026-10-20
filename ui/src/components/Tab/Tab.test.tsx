import { render, screen } from '@testing-library/react'
import type { Notation, NoteEvent } from '../../notation/types'
import { Tab } from './Tab'

const ev = (
  t: number,
  string: number,
  fret: number,
  extra: Partial<NoteEvent> = {},
): NoteEvent => ({ t, dur: 1, string, fret, ...extra })

const make = (
  events: NoteEvent[],
  extra: Partial<Notation> = {},
): Notation => ({
  bpm: 60,
  time_signature: '4/4',
  tuning: ['E2', 'A2', 'D3', 'G3', 'B3', 'E4'],
  events,
  ...extra,
})

describe('Tab', () => {
  it('es una imagen accesible con etiqueta en español', () => {
    render(
      <Tab
        notation={make([ev(0, 1, 5), ev(1, 2, 7)])}
        activeIndex={null}
        width={640}
      />,
    )
    const img = screen.getByRole('img')
    expect(img).toHaveAttribute(
      'aria-label',
      expect.stringMatching(/tablatura/i),
    )
    expect(img.getAttribute('aria-label')).toMatch(/2 notas/)
  })

  it('dibuja seis cuerdas con sus nombres según la afinación', () => {
    const { container } = render(
      <Tab notation={make([ev(0, 1, 5)])} activeIndex={null} width={640} />,
    )
    const names = [
      ...container.querySelectorAll('[data-role="string-name"]'),
    ].map((n) => n.textContent)
    expect(names).toEqual(['e', 'B', 'G', 'D', 'A', 'E'])
    expect(
      container.querySelectorAll('[data-role="string-line"]'),
    ).toHaveLength(6)
  })

  it('usa la afinación recibida para los nombres', () => {
    const { container } = render(
      <Tab
        notation={make([ev(0, 1, 5)], {
          tuning: ['D2', 'A2', 'D3', 'G3', 'B3', 'E4'],
        })}
        activeIndex={null}
        width={640}
      />,
    )
    const names = [
      ...container.querySelectorAll('[data-role="string-name"]'),
    ].map((n) => n.textContent)
    expect(names[5]).toBe('D')
  })

  it('dibuja el número de traste de cada nota', () => {
    const { container } = render(
      <Tab
        notation={make([ev(0, 3, 12), ev(1, 4, 0)])}
        activeIndex={null}
        width={640}
      />,
    )
    const frets = [...container.querySelectorAll('[data-role="fret"]')].map(
      (n) => n.textContent,
    )
    expect(frets).toEqual(['12', '0'])
  })

  it('pone los eventos simultáneos en la misma columna', () => {
    const { container } = render(
      <Tab
        notation={make([ev(0, 6, 0), ev(0, 5, 2)])}
        activeIndex={null}
        width={640}
      />,
    )
    const xs = [...container.querySelectorAll('[data-role="fret"]')].map((n) =>
      n.getAttribute('x'),
    )
    expect(new Set(xs).size).toBe(1)
  })

  it.each([
    [{ technique: 'h' as const }, 'h'],
    [{ technique: 'p' as const }, 'p'],
    [{ technique: '/' as const }, '/'],
    [{ technique: '\\' as const }, '\\'],
    [{ technique: 'b' as const, bend: 1 }, 'b1'],
    [{ technique: 'r' as const }, 'r'],
    [{ technique: '~' as const }, '~'],
    [{ technique: 'pm' as const }, 'PM'],
  ])('anota la técnica %j como %s', (extra, text) => {
    const { container } = render(
      <Tab
        notation={make([ev(0, 2, 5), ev(1, 2, 7, extra)])}
        activeIndex={null}
        width={640}
      />,
    )
    const labels = [
      ...container.querySelectorAll('[data-role="technique"]'),
    ].map((n) => n.textContent)
    expect(labels).toEqual([text])
  })

  it('ejemplo del plan: la h queda entre el 5 y el 7', () => {
    const { container } = render(
      <Tab
        notation={make([ev(0, 6, 5), ev(1, 6, 7, { technique: 'h' })])}
        activeIndex={null}
        width={640}
      />,
    )
    const [five, seven] = [
      ...container.querySelectorAll('[data-role="fret"]'),
    ].map((n) => Number(n.getAttribute('x')))
    const h = container.querySelector('[data-role="technique"]')
    expect(Number(h?.getAttribute('x'))).toBe((five + seven) / 2)
  })

  it('la ligadura que cruza de sistema se dibuja en el borde izquierdo del nuevo', () => {
    const events = Array.from({ length: 16 }, (_, i) =>
      ev(i, 1, i, i === 8 ? { technique: 'h' } : {}),
    )
    const { container } = render(
      <Tab notation={make(events)} activeIndex={null} width={300} />,
    )
    const systems = container.querySelectorAll('svg')
    expect(systems[0].querySelectorAll('[data-role="technique"]')).toHaveLength(
      0,
    )
    const h = systems[1].querySelector('[data-role="technique"]')
    const firstFret = systems[1].querySelector('[data-role="fret"]')
    expect(Number(h?.getAttribute('x'))).toBeLessThan(
      Number(firstFret?.getAttribute('x')),
    )
  })

  it('x se dibuja como nota muerta sobre la cuerda', () => {
    const { container } = render(
      <Tab
        notation={make([ev(0, 2, 0, { technique: 'x' })])}
        activeIndex={null}
        width={640}
      />,
    )
    expect(container.querySelector('[data-role="fret"]')).toHaveTextContent('x')
    expect(container.querySelectorAll('[data-role="technique"]')).toHaveLength(
      0,
    )
  })

  it('resalta solo la columna del evento activo', () => {
    const { container } = render(
      <Tab
        notation={make([ev(0, 1, 5), ev(1, 2, 7), ev(1, 3, 9)])}
        activeIndex={2}
        width={640}
      />,
    )
    const active = [...container.querySelectorAll('[data-active="true"]')]
    expect(active.map((n) => n.textContent)).toEqual(['7', '9'])
    expect(
      container.querySelectorAll('[data-role="note"][data-active="false"]'),
    ).toHaveLength(1)
  })

  it('sin evento activo no resalta nada', () => {
    const { container } = render(
      <Tab notation={make([ev(0, 1, 5)])} activeIndex={null} width={640} />,
    )
    expect(container.querySelectorAll('[data-active="true"]')).toHaveLength(0)
  })

  it('parte en varios sistemas cuando no entra en el ancho', () => {
    const events = Array.from({ length: 16 }, (_, i) => ev(i, 1, i))
    const wide = render(
      <Tab notation={make(events)} activeIndex={null} width={1200} />,
    )
    expect(wide.container.querySelectorAll('svg')).toHaveLength(1)
    wide.unmount()
    const narrow = render(
      <Tab notation={make(events)} activeIndex={null} width={300} />,
    )
    expect(narrow.container.querySelectorAll('svg').length).toBeGreaterThan(1)
  })

  it('no rompe sin eventos', () => {
    render(<Tab notation={make([])} activeIndex={null} width={640} />)
    expect(screen.getByRole('img')).toBeInTheDocument()
  })

  it('no usa colores fijos', () => {
    const { container } = render(
      <Tab
        notation={make([ev(0, 1, 5, { technique: 'h' })])}
        activeIndex={0}
        width={640}
      />,
    )
    expect(container.innerHTML).not.toMatch(/#[0-9a-f]{3,8}\b|rgb\(|hsl\(/i)
  })
})
