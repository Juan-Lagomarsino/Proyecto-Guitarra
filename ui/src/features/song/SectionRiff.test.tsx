import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useEffect } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  BackingProvider,
  usePublishBacking,
} from '../../backing/BackingContext'
import { useBackingSync } from '../../backing/useBackingSync'
import type { SongChartContent } from '../../songs/types'
import songCss from './song.css?raw'
import { PracticeSection } from './PracticeSection'
import { SectionDetail } from './SectionDetail'

// bpm 60 y grilla de 1 beat por segundo: segundos == beats.
const content = {
  instrument: 'electric',
  bpm: 60,
  beat_grid: { beats_s: Array.from({ length: 41 }, (_, i) => i) },
  sections: [
    {
      id: 'verso',
      name: 'Verso',
      start_s: 10,
      end_s: 30,
      order: 0,
      chord_source: 'detected',
      riff: {
        bpm: 60,
        events: [
          { t: 0, dur: 1, string: 5, fret: 3, confidence: 0.9 },
          { t: 1, dur: 1, string: 4, fret: 5, confidence: 0.3 },
          { t: 1, dur: 1, string: 3, fret: 7 },
        ],
      },
    },
  ],
} as unknown as SongChartContent

let setPosition: (seconds: number) => void = () => undefined
function Controller() {
  const publisher = usePublishBacking()
  useEffect(() => {
    setPosition = (s) => act(() => publisher.setPosition(s))
  }, [publisher])
  return null
}

function Harness({ withRiff = true }: { withRiff?: boolean }) {
  const sync = useBackingSync(content)
  const section = withRiff
    ? content.sections[0]
    : { ...content.sections[0], riff: null }
  return (
    <SectionDetail
      section={section}
      instrument="electric"
      sync={sync.forSection(section)}
    />
  )
}

const renderRiff = (withRiff = true) =>
  render(
    <BackingProvider>
      <Controller />
      <Harness withRiff={withRiff} />
    </BackingProvider>,
  )

afterEach(() => vi.unstubAllGlobals())

describe('riff de la sección', () => {
  it('muestra el bloque Riff con tab y mástil', () => {
    const { container } = renderRiff()
    const block = screen.getByRole('region', { name: 'Riff' })
    expect(within(block).getByRole('img', { name: /Tablatura/ })).toBeTruthy()
    expect(within(block).getByRole('img', { name: /Mástil/ })).toBeTruthy()
    expect(container.querySelectorAll('[data-role="note"]')).toHaveLength(3)
  })

  it('marca la baja confianza en tab y mástil, con leyenda; sin confidence es normal', () => {
    const { container } = renderRiff()
    const low = container.querySelectorAll(
      '[data-role="note"][data-confidence="low"]',
    )
    expect(low).toHaveLength(1)
    expect(low[0].textContent).toBe('5')
    const board = container.querySelectorAll(
      '[data-testid="note"][data-confidence="low"]',
    )
    expect(board).toHaveLength(1)
    expect(board[0].getAttribute('data-string')).toBe('4')
    expect(board[0].getAttribute('stroke-dasharray')).toBeTruthy()
    expect(screen.getByText(/poco seguro/i)).toBeTruthy()
  })

  it('un riff sin ninguna nota dudosa no muestra la leyenda', () => {
    const sure = {
      ...content.sections[0],
      riff: { bpm: 60, events: [{ t: 0, dur: 1, string: 5, fret: 3 }] },
    }
    render(<SectionDetail section={sure} instrument="electric" />)
    expect(screen.queryByText(/poco seguro/i)).toBeNull()
  })

  it('sin riff no aparece nada nuevo', () => {
    const { container } = renderRiff(false)
    expect(screen.queryByRole('region', { name: 'Riff' })).toBeNull()
    expect(container.querySelector('[data-role="note"]')).toBeNull()
  })

  it('resalta todas las notas que suenan según la posición', () => {
    const { container } = renderRiff()
    const active = () =>
      container.querySelectorAll('[data-testid="note"][data-state="active"]')
    expect(active()).toHaveLength(0)

    setPosition(11.5) // beat 1.5: las dos notas de t=1
    expect(active()).toHaveLength(2)
    expect(
      container.querySelectorAll('[data-role="note"][data-active="true"]'),
    ).toHaveLength(2)

    setPosition(10.2)
    expect(active()).toHaveLength(1)

    setPosition(5) // fuera de la sección
    expect(active()).toHaveLength(0)
  })
})

describe('Practicar esta sección con riff', () => {
  const props = {
    songId: 7,
    sectionId: 12,
    sectionName: 'Verso',
    instrument: 'electric' as const,
    onCreated: () => undefined,
  }

  it('ofrece el tipo riff solo si hay riff y lo manda a la API', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn(async () => new Response('{}', { status: 201 }))
    vi.stubGlobal('fetch', fetchMock)
    const { rerender } = render(<PracticeSection {...props} />)
    await user.click(screen.getByRole('button', { name: /practicar/i }))
    expect(screen.queryByRole('button', { name: 'Riff' })).toBeNull()

    rerender(<PracticeSection {...props} hasRiff />)
    await user.click(screen.getByRole('button', { name: 'Riff' }))
    await user.click(screen.getByRole('button', { name: /crear ejercicio/i }))
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ]
    expect(url).toContain('/songs/7/sections/12/exercises')
    expect(JSON.parse(init.body as string)).toEqual({
      type: 'riff',
      instrument: 'electric',
    })
  })
})

describe('riff a 375 px', () => {
  it('el bloque no fija anchos y deja que tab y mástil encojan', () => {
    const block = /\.song-riff[^{]*\{[^}]*\}/g
    const rules = songCss.match(block)?.join('\n') ?? ''
    expect(rules).toMatch(/min-width:\s*0/)
    expect(rules).not.toMatch(/(^|[^-])width:\s*\d{3,}px/)
  })
})
