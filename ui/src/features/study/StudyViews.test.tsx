import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFetch } from '../../api/client'
import { StudyRoutes } from './StudyRoutes'

vi.mock('../../api/client', () => ({ apiFetch: vi.fn() }))
const apiFetchMock = vi.mocked(apiFetch)

const levels = [
  {
    id: 1,
    slug: 'n1',
    position: 1,
    name: 'Primeros pasos',
    description: 'Cuerdas al aire',
    instrument: 'electric',
  },
  {
    id: 2,
    slug: 'n2',
    position: 2,
    name: 'Escalas',
    description: 'Pentatónica',
    instrument: 'electric',
  },
]
const lessons = [
  { id: 10, level_id: 1, slug: 'l1', position: 1, title: 'Postura' },
]
const lesson = {
  ...lessons[0],
  content_md: '# Teoría\n\nSentate **derecho**.',
  exercises: [
    {
      id: 7,
      lesson_id: 10,
      slug: 'e1',
      title: 'Cuerdas al aire',
      type: 'scale',
      instrument: 'electric',
      category: 'warmup',
      bpm_start: 60,
      bpm_target: 80,
      duration_min: 3,
      notation: {
        bpm: 60,
        events: [{ t: 0, dur: 1, string: 6, fret: 0 }],
      },
    },
  ],
}

const progressSummary = {
  current_streak: 0,
  max_streak: 0,
  practiced_days: 0,
  songs_in_progress: 0,
  levels: [
    {
      level_id: 1,
      slug: 'n1',
      position: 1,
      name: 'Primeros pasos',
      completed: 3,
      total: 8,
    },
  ],
}

function routeApi(overrides: Record<string, unknown> = {}) {
  const table: Record<string, unknown> = {
    '/levels': levels,
    '/levels/1/lessons': lessons,
    '/lessons/10': lesson,
    '/progress/summary': progressSummary,
    '/exercises/7': { ...lesson.exercises[0], best_bpm: 70 },
    ...overrides,
  }
  apiFetchMock.mockImplementation(async (path) => {
    const value = table[path]
    if (value instanceof Error) throw value
    if (value === undefined) throw new Error(`sin mock para ${path}`)
    return value
  })
}

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="estudio/*" element={<StudyRoutes />} />
      </Routes>
    </MemoryRouter>,
  )

beforeEach(() => {
  apiFetchMock.mockReset()
})

describe('vistas de Estudio', () => {
  it('lista los niveles, con estado de carga previo', async () => {
    routeApi()
    renderAt('/estudio')
    expect(screen.getByRole('status')).toHaveTextContent(/cargando/i)
    expect(
      await screen.findByRole('link', { name: /primeros pasos/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /escalas/i })).toBeInTheDocument()
  })

  it('muestra el avance por nivel cruzando por level_id', async () => {
    routeApi()
    renderAt('/estudio')
    expect(await screen.findByText('3/8 completados')).toBeInTheDocument()
    const bar = screen.getByRole('progressbar', {
      name: /avance de primeros pasos/i,
    })
    expect(bar).toHaveAttribute('value', '3')
    expect(bar).toHaveAttribute('max', '8')
    expect(screen.getAllByRole('progressbar')).toHaveLength(1)
  })

  it('si falla el summary, la lista se ve igual sin avance', async () => {
    routeApi({ '/progress/summary': new Error('caído') })
    renderAt('/estudio')
    expect(
      await screen.findByRole('link', { name: /primeros pasos/i }),
    ).toBeInTheDocument()
    await waitFor(() =>
      expect(apiFetchMock).toHaveBeenCalledWith('/progress/summary'),
    )
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })

  it('muestra un error si fallan los niveles', async () => {
    routeApi({ '/levels': new Error('API caída') })
    renderAt('/estudio')
    expect(await screen.findByRole('alert')).toHaveTextContent(/API caída/)
  })

  it('navega de nivel a lección y de lección a sus ejercicios', async () => {
    const user = userEvent.setup()
    routeApi()
    renderAt('/estudio')

    await user.click(
      await screen.findByRole('link', { name: /primeros pasos/i }),
    )
    await user.click(await screen.findByRole('link', { name: /postura/i }))

    expect(
      await screen.findByRole('heading', { name: 'Teoría' }),
    ).toBeInTheDocument()
    expect(screen.getByText('derecho').tagName).toBe('STRONG')
    const card = await screen.findByRole('article')
    expect(
      within(card).getByRole('heading', { name: 'Cuerdas al aire' }),
    ).toBeInTheDocument()
    expect(await within(card).findByText(/tu mejor/i)).toHaveTextContent(
      '70 bpm',
    )
  })

  it('muestra un error si falla la lección', async () => {
    routeApi({ '/lessons/10': new Error('no existe') })
    renderAt('/estudio/lecciones/10')
    expect(await screen.findByRole('alert')).toHaveTextContent(/no existe/)
  })

  it('un nivel sin lecciones lo dice', async () => {
    routeApi({ '/levels/1/lessons': [] })
    renderAt('/estudio/niveles/1')
    expect(await screen.findByText(/todavía no tiene lecciones/i)).toBeVisible()
  })
})
