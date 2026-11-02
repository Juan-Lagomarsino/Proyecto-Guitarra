import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { SongChartResponse, SongDetail } from '../../api/songs'
import type { Exercise } from '../study/types'
import { SongScreen } from './SongScreen'

const json = (body: unknown, status = 200, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })

const song: SongDetail = {
  id: 7,
  title: 'Come Together',
  artist: 'The Beatles',
  source: 'youtube',
  analysis_status: 'ready',
  current_step: null,
  bpm: 82,
  key: 'Dm',
  created_at: '2026-10-20T10:00:00Z',
  url: null,
  error: null,
  duration_s: 259,
  year: 1969,
  has_cifra: false,
  cifra_url: null,
  audio: [],
  separation_status: 'none',
  sections: [
    {
      id: 11,
      slug: 'intro',
      name: 'Intro',
      start_s: 0,
      end_s: 20,
      position: 0,
      stale: false,
    },
    {
      id: 12,
      slug: 'estrofa',
      name: 'Estrofa',
      start_s: 20,
      end_s: 60,
      position: 1,
      stale: false,
    },
  ],
}

const chart: SongChartResponse = {
  song_id: 7,
  instrument: 'classical',
  version: 1,
  origin: 'auto',
  confidence: 0.7,
  created_at: '2026-10-20T10:00:00Z',
  content: {
    instrument: 'classical',
    bpm: 82,
    sections: [
      {
        id: 'intro',
        name: 'Intro',
        start_s: 0,
        end_s: 20,
        order: 0,
        chord_source: 'detected',
        chords: [
          { t_s: 0, name: 'Am', shape: ['x', 0, 2, 2, 1, 0], confidence: 0.9 },
        ],
      },
      {
        id: 'estrofa',
        name: 'Estrofa',
        start_s: 20,
        end_s: 60,
        order: 1,
        chord_source: 'detected',
        chords: [
          { t_s: 20, name: 'G', shape: [3, 2, 0, 0, 0, 3], confidence: 0.9 },
        ],
      },
    ],
  } as SongChartResponse['content'],
}

const created: Exercise = {
  id: 40,
  lesson_id: null,
  song_section_id: 12,
  slug: 'cancion-7-estrofa-strumming-ab12cd',
  title: 'Come Together · Estrofa: rasgueo',
  type: 'strumming',
  instrument: 'classical',
  category: 'technique',
  description: 'Rasguá el patrón de la sección.',
  bpm_start: 57,
  bpm_target: 82,
  duration_min: 5,
  notation: {
    bpm: 57,
    chords: [{ t: 0, name: 'G', shape: [3, 2, 0, 0, 0, 3] }],
    strum: [{ t: 0, pattern: 'D-DU-UDU', accent: [] }],
  },
}

interface Api {
  calls: { path: string; method: string; body?: unknown }[]
  exercises: Exercise[]
}

function mockApi(createResponse?: () => Response): Api {
  const api: Api = { calls: [], exercises: [] }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const path = url.replace('/api/v1', '')
      const method = init?.method ?? 'GET'
      const body = init?.body ? JSON.parse(init.body as string) : undefined
      api.calls.push({ path, method, body })
      if (path === '/songs/7') return json(song)
      if (path === '/songs/7/chart?instrument=classical') return json(chart)
      if (path === '/songs/7/exercises') return json(api.exercises)
      if (path === '/songs/7/sections/12/exercises') {
        if (createResponse) return createResponse()
        api.exercises = [created]
        return json(created, 201)
      }
      if (path === '/exercises/40') return json({ ...created, best_bpm: null })
      if (path === '/exercises/40/complete')
        return json(
          {
            id: 1,
            exercise_id: 40,
            completed_at: '2026-10-23T12:00:00Z',
            bpm_logrado: body.bpm_logrado,
            instrumento: body.instrumento,
            best_bpm: body.bpm_logrado,
          },
          201,
        )
      return json({ detail: 'no existe' }, 404)
    }),
  )
  return api
}

const renderScreen = () =>
  render(
    <MemoryRouter initialEntries={['/explorar/canciones/7']}>
      <Routes>
        <Route path="explorar/canciones/:id" element={<SongScreen />} />
      </Routes>
    </MemoryRouter>,
  )

async function selectEstrofa(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByRole('article', { name: 'Sección Intro' })
  const timeline = screen.getByRole('list', { name: 'Secciones de la canción' })
  await user.click(within(timeline).getByRole('button', { name: /Estrofa/ }))
}

afterEach(() => vi.unstubAllGlobals())

describe('Practicar una sección', () => {
  it('crea el ejercicio del tipo elegido para la sección seleccionada y lo lista', async () => {
    const user = userEvent.setup()
    const api = mockApi()
    renderScreen()
    await selectEstrofa(user)

    await user.click(
      screen.getByRole('button', { name: 'Practicar esta sección' }),
    )
    await user.click(screen.getByRole('button', { name: 'Rasgueo' }))
    await user.click(screen.getByRole('button', { name: 'Crear ejercicio' }))

    const post = api.calls.find((call) => call.method === 'POST')
    expect(post).toEqual({
      path: '/songs/7/sections/12/exercises',
      method: 'POST',
      body: { type: 'strumming', instrument: 'classical' },
    })
    const list = await screen.findByRole('region', { name: 'Tus ejercicios' })
    expect(
      await within(list).findByRole('heading', {
        name: 'Come Together · Estrofa: rasgueo',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Listo, el ejercicio/)).toBeInTheDocument()
  })

  it('por defecto crea cambio de acordes', async () => {
    const user = userEvent.setup()
    const api = mockApi()
    renderScreen()
    await selectEstrofa(user)
    await user.click(
      screen.getByRole('button', { name: 'Practicar esta sección' }),
    )
    await user.click(screen.getByRole('button', { name: 'Crear ejercicio' }))
    await screen.findByRole('region', { name: 'Tus ejercicios' })
    expect(api.calls.find((c) => c.method === 'POST')?.body).toEqual({
      type: 'chords',
      instrument: 'classical',
    })
  })

  it('muestra el motivo si la API no puede crearlo', async () => {
    const user = userEvent.setup()
    mockApi(() =>
      json({ detail: "La sección 'Estrofa' no tiene rasgueo" }, 422),
    )
    renderScreen()
    await selectEstrofa(user)
    await user.click(
      screen.getByRole('button', { name: 'Practicar esta sección' }),
    )
    await user.click(screen.getByRole('button', { name: 'Crear ejercicio' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /no tiene rasgueo/,
    )
  })

  it('se puede cancelar sin crear nada', async () => {
    const user = userEvent.setup()
    const api = mockApi()
    renderScreen()
    await selectEstrofa(user)
    await user.click(
      screen.getByRole('button', { name: 'Practicar esta sección' }),
    )
    await user.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(
      screen.getByRole('button', { name: 'Practicar esta sección' }),
    ).toBeInTheDocument()
    expect(api.calls.some((call) => call.method === 'POST')).toBe(false)
  })

  it('los ejercicios de la canción se completan con Terminé', async () => {
    const user = userEvent.setup()
    const api = mockApi()
    api.exercises = [created]
    renderScreen()
    const list = await screen.findByRole('region', { name: 'Tus ejercicios' })
    await within(list).findByRole('heading', {
      name: 'Come Together · Estrofa: rasgueo',
    })
    await user.click(within(list).getByRole('button', { name: 'Terminé' }))
    expect(await within(list).findByText(/Tu mejor/)).toHaveTextContent(
      '57 bpm',
    )
    const complete = api.calls.find((c) => c.path === '/exercises/40/complete')
    expect(complete?.body).toEqual({
      bpm_logrado: 57,
      instrumento: 'classical',
    })
  })

  it('sin ejercicios no muestra la lista', async () => {
    const user = userEvent.setup()
    mockApi()
    renderScreen()
    await selectEstrofa(user)
    expect(screen.queryByText('Tus ejercicios')).not.toBeInTheDocument()
  })
})
