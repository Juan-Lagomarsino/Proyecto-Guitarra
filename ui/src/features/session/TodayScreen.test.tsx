import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFetch } from '../../api/client'
import type { TodaySession } from '../../api/session'
import { TodayScreen } from './TodayScreen'

vi.mock('../../api/client', () => ({ apiFetch: vi.fn() }))
const apiFetchMock = vi.mocked(apiFetch)

const exercise = (id: number, category: string, done = false) => ({
  id,
  title: `Ejercicio ${id}`,
  category,
  minutes: 5,
  duration_min: 5,
  bpm_target: 80,
  completed_today: done,
  description: null,
})

const session: TodaySession = {
  date: '2026-10-23',
  seed: 1,
  status: 'pending',
  total_minutes: 20,
  blocks: [
    {
      category: 'warmup',
      minutes: 5,
      exercises: [exercise(1, 'warmup', true)],
    },
    {
      category: 'technique',
      minutes: 10,
      exercises: [exercise(2, 'technique'), exercise(3, 'technique')],
    },
    { category: 'riff', minutes: 5, exercises: [exercise(4, 'riff')] },
  ],
}

const regenerated: TodaySession = {
  ...session,
  seed: 2,
  total_minutes: 15,
  blocks: [
    {
      category: 'improvisation',
      minutes: 15,
      exercises: [exercise(9, 'improvisation')],
    },
  ],
}

const detailOf = (id: number) => ({
  id,
  lesson_id: 1,
  slug: `e${id}`,
  title: `Ejercicio ${id}`,
  type: 'scale',
  instrument: 'electric',
  category: 'warmup',
  bpm_start: 60,
  bpm_target: 80,
  duration_min: 5,
  notation: { bpm: 60, events: [{ t: 0, dur: 1, string: 6, fret: 0 }] },
  best_bpm: null,
})

function mockApi(today: unknown = session) {
  apiFetchMock.mockImplementation(async (path) => {
    if (path === '/sessions/today') {
      if (today instanceof Error) throw today
      return today
    }
    if (path === '/sessions/today/regenerate') return regenerated
    const match = /^\/exercises\/(\d+)(\/complete)?$/.exec(path)
    if (match && match[2])
      return { id: 1, exercise_id: Number(match[1]), best_bpm: 60 }
    if (match) return detailOf(Number(match[1]))
    throw new Error(`sin mock para ${path}`)
  })
}

const renderScreen = () =>
  render(
    <MemoryRouter>
      <TodayScreen />
    </MemoryRouter>,
  )

beforeEach(() => {
  apiFetchMock.mockReset()
})

describe('TodayScreen', () => {
  it('muestra fecha, duración total y bloques en orden con títulos en español', async () => {
    mockApi()
    renderScreen()
    expect(screen.getByRole('status')).toHaveTextContent(/cargando/i)
    expect(await screen.findByText(/23 de octubre/i)).toHaveTextContent(
      '20 min',
    )
    const titles = Array.from(
      document.querySelectorAll('.session-block__title'),
    ).map((h) => h.textContent)
    expect(titles).toEqual(['Calentamiento5 min', 'Técnica10 min', 'Riff5 min'])
    expect(await screen.findAllByRole('article')).toHaveLength(4)
  })

  it('marca lo hecho hoy y resume', async () => {
    mockApi()
    renderScreen()
    expect(await screen.findByText('1 de 4 hechos')).toBeInTheDocument()
    expect(screen.getAllByText(/hecho hoy/i)).toHaveLength(1)
  })

  it('Terminé marca la tarjeta y actualiza el resumen sin recargar', async () => {
    const user = userEvent.setup()
    mockApi()
    renderScreen()
    const cards = await screen.findAllByRole('article')
    await user.click(within(cards[1]).getByRole('button', { name: 'Terminé' }))
    expect(await screen.findByText('2 de 4 hechos')).toBeInTheDocument()
    expect(screen.getAllByText(/hecho hoy/i)).toHaveLength(2)
  })

  it('Regenerar llama al POST y muestra la nueva sesión', async () => {
    const user = userEvent.setup()
    mockApi()
    renderScreen()
    await screen.findByText('1 de 4 hechos')
    await user.click(screen.getByRole('button', { name: 'Regenerar' }))
    expect(apiFetchMock).toHaveBeenCalledWith('/sessions/today/regenerate', {
      method: 'POST',
    })
    expect(await screen.findByText('0 de 1 hechos')).toBeInTheDocument()
    expect(screen.getByText('Improvisación')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Regenerar' })).toBeEnabled()
  })

  it('deshabilita Regenerar mientras la llamada está en curso', async () => {
    const user = userEvent.setup()
    mockApi()
    renderScreen()
    await screen.findByText('1 de 4 hechos')
    await screen.findAllByRole('article')
    let release: () => void = () => undefined
    apiFetchMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          release = () => resolve(regenerated)
        }),
    )
    await user.click(screen.getByRole('button', { name: 'Regenerar' }))
    expect(screen.getByRole('button', { name: /regenerando/i })).toBeDisabled()
    release()
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Regenerar' })).toBeEnabled(),
    )
  })

  it('estado vacío con link a Estudio', async () => {
    mockApi({ ...session, total_minutes: 0, blocks: [] })
    renderScreen()
    expect(await screen.findByText(/no hay ejercicios/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Estudio' })).toHaveAttribute(
      'href',
      '/estudio',
    )
  })

  it('una respuesta sin blocks es un error de carga, no rompe la app', async () => {
    mockApi({ theme_tokens: {} })
    renderScreen()
    expect(await screen.findByRole('alert')).toHaveTextContent(/formato/i)
  })

  it('muestra un error si falla la carga', async () => {
    mockApi(new Error('API caída'))
    renderScreen()
    expect(await screen.findByRole('alert')).toHaveTextContent(/API caída/)
  })
})
