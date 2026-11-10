import { act, render, screen, within } from '@testing-library/react'
import { useEffect } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { SongSectionInfo } from '../../api/songs'
import {
  BackingProvider,
  usePublishBacking,
} from '../../backing/BackingContext'
import { useBackingSync } from '../../backing/useBackingSync'
import type { SongChartContent } from '../../songs/types'
import type { Exercise } from '../study/types'
import { SectionDetail } from './SectionDetail'
import { SectionTimeline } from './SectionTimeline'
import { SongExercises } from './SongExercises'

// bpm 60 y grilla de 1 beat por segundo: segundos == beats.
const content = {
  instrument: 'classical',
  bpm: 60,
  beat_grid: { beats_s: Array.from({ length: 41 }, (_, i) => i) },
  sections: [
    {
      id: 'intro',
      name: 'Intro',
      start_s: 0,
      end_s: 10,
      order: 0,
      chord_source: 'detected',
    },
    {
      id: 'estrofa',
      name: 'Estrofa',
      start_s: 10,
      end_s: 30,
      order: 1,
      chord_source: 'detected',
      chords: [
        { t_s: 10, name: 'Am', shape: ['x', 0, 2, 2, 1, 0], confidence: 0.9 },
        { t_s: 14, name: 'G', shape: [3, 2, 0, 0, 0, 3], confidence: 0.9 },
      ],
      strum: {
        pattern: 'DUDU',
        beats_per_cycle: 4,
        pattern_id: 'p',
        confidence: 0.9,
      },
    },
  ],
} as unknown as SongChartContent

const storedSections: SongSectionInfo[] = [
  {
    id: 12,
    slug: 'estrofa',
    name: 'Estrofa',
    start_s: 10,
    end_s: 30,
    position: 1,
    stale: false,
  },
]

const exercise: Exercise = {
  id: 40,
  lesson_id: null,
  song_section_id: 12,
  slug: 'x',
  title: 'Estrofa: línea',
  type: 'melody',
  instrument: 'classical',
  category: 'technique',
  bpm_start: 60,
  bpm_target: 60,
  duration_min: 5,
  notation: {
    bpm: 60,
    events: [
      { t: 0, dur: 1, string: 2, fret: 1 },
      { t: 1, dur: 1, string: 3, fret: 2 },
      { t: 1, dur: 1, string: 4, fret: 0 },
    ],
  },
}

/** Publica la posición controlada por el test. */
let setPosition: (seconds: number) => void = () => undefined
function Controller() {
  const publisher = usePublishBacking()
  useEffect(() => {
    setPosition = (s) => act(() => publisher.setPosition(s))
  }, [publisher])
  return null
}

function Harness() {
  const sync = useBackingSync(content)
  const estrofa = content.sections[1]
  return (
    <>
      <SectionTimeline
        sections={[...content.sections]}
        selectedId="intro"
        onSelect={() => undefined}
        playingId={sync.activeSection?.id ?? null}
      />
      <SectionDetail
        section={estrofa}
        instrument="classical"
        sync={sync.forSection(estrofa)}
      />
      <SongExercises
        songId={7}
        refreshKey={0}
        sections={storedSections}
        content={content}
      />
    </>
  )
}

function renderHarness() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify([exercise]))),
  )
  return render(
    <BackingProvider>
      <Controller />
      <Harness />
    </BackingProvider>,
  )
}

const now = (container: HTMLElement) =>
  Array.from(container.querySelectorAll('[data-now="true"]')).map(
    (el) => el.textContent,
  )

afterEach(() => vi.unstubAllGlobals())

describe('sincronía con el acompañamiento', () => {
  it('sin posición no se marca nada', async () => {
    const { container } = renderHarness()
    await screen.findByText('Estrofa: línea')
    expect(now(container)).toEqual([])
  })

  it('marca la sección, el acorde y el golpe que suenan', async () => {
    renderHarness()
    await screen.findByText('Estrofa: línea')

    setPosition(15.2)
    const timeline = screen.getByRole('list', {
      name: 'Secciones de la canción',
    })
    expect(
      within(timeline)
        .getByRole('button', { name: /Estrofa/ })
        .getAttribute('data-now'),
    ).toBe('true')
    expect(
      within(timeline)
        .getByRole('button', { name: /Intro/ })
        .getAttribute('data-now'),
    ).toBeNull()
    // acorde G (t=14) y golpe 'U' (beat 5.2 -> fase 1.2/4 -> celda 1)
    const progression = screen.getByRole('list', { name: 'Progresión' })
    expect(now(progression as HTMLElement)).toEqual(['G'])
    const pattern = screen.getByRole('group', { name: 'Rasgueo DUDU' })
    expect(now(pattern)).toEqual(['U'])
  })

  it('marca la nota activa en mástil y tab, y vuelve con el loop', async () => {
    const { container } = renderHarness()
    await screen.findByText('Estrofa: línea')

    setPosition(11.5) // beat 1.5 de la sección: segunda nota (cuerda 3, traste 2)
    const active = () =>
      container.querySelectorAll('[data-testid="note"][data-state="active"]')
    expect(active()).toHaveLength(2) // las dos notas del acorde en t=1
    expect(active()[0].getAttribute('data-fret')).toBe('2')
    expect(
      container.querySelectorAll('[data-role="note"][data-active="true"]'),
    ).toHaveLength(2)

    setPosition(10.2) // el loop vuelve al inicio: primera nota
    expect(active()).toHaveLength(1)
    expect(active()[0].getAttribute('data-fret')).toBe('1')

    setPosition(5) // fuera de la sección: nada
    expect(active()).toHaveLength(0)
  })
})
