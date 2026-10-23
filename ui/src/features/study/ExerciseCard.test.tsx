import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFetch } from '../../api/client'
import { FakeAudio } from '../../playback/fakeClock'
import { ExerciseCard } from './ExerciseCard'
import type { Exercise, ExerciseDetail } from './types'

vi.mock('../../api/client', () => ({ apiFetch: vi.fn() }))
const apiFetchMock = vi.mocked(apiFetch)

const exercise: Exercise = {
  id: 7,
  lesson_id: 2,
  slug: 'escala-la-menor',
  title: 'Escala de La menor',
  type: 'scale',
  instrument: 'electric',
  category: 'technique',
  description: 'Subí y bajá la escala sin apurarte.',
  bpm_start: 60,
  bpm_target: 100,
  duration_min: 5,
  notation: {
    bpm: 60,
    tonic: 'A',
    events: [
      { t: 0, dur: 1, string: 6, fret: 5 },
      { t: 1, dur: 1, string: 5, fret: 7 },
    ],
  },
}

const detail = (best: number | null): ExerciseDetail => ({
  ...exercise,
  best_bpm: best,
})

const audio = new FakeAudio()
const audioFactory = () => audio

function renderCard(props: Partial<Parameters<typeof ExerciseCard>[0]> = {}) {
  return render(
    <ExerciseCard exercise={exercise} audio={audioFactory} {...props} />,
  )
}

const activeTabNotes = (container: HTMLElement) =>
  container.querySelectorAll('[data-role="note"][data-active="true"]')
const activeBoardNotes = (container: HTMLElement) =>
  container.querySelectorAll('[data-state="active"]')

beforeEach(() => {
  apiFetchMock.mockReset()
})

describe('ExerciseCard', () => {
  it('con best_bpm ya conocido no pide el ejercicio y usa ese valor', async () => {
    renderCard({ exercise: { ...exercise, best_bpm: 90 } })
    expect(await screen.findByText(/tu mejor/i)).toHaveTextContent('90 bpm')
    expect(apiFetchMock).not.toHaveBeenCalled()
  })

  it('sin best_bpm lo pide a la API', async () => {
    apiFetchMock.mockResolvedValue(detail(70))
    renderCard()
    expect(await screen.findByText(/tu mejor/i)).toHaveTextContent('70 bpm')
    expect(apiFetchMock).toHaveBeenCalledTimes(1)
  })

  it('sin descripción no muestra el bloque', async () => {
    apiFetchMock.mockResolvedValue(detail(null))
    const { container } = renderCard({
      exercise: { ...exercise, description: null },
    })
    await screen.findByText(/sin marca/i)
    expect(
      container.querySelector('.exercise-card__description'),
    ).not.toBeInTheDocument()
  })

  it('muestra categoría, título, chips, mástil y tab', async () => {
    apiFetchMock.mockResolvedValue(detail(80))
    renderCard()

    expect(screen.getByText('Técnica')).toBeInTheDocument()
    expect(
      screen.getByText('Subí y bajá la escala sin apurarte.'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Escala de La menor' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/objetivo/i)).toHaveTextContent('100 bpm')
    expect(await screen.findByText(/tu mejor/i)).toHaveTextContent('80 bpm')
    expect(screen.getByRole('img', { name: /mástil/i })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /tablatura/i })).toBeInTheDocument()
    expect(apiFetchMock).toHaveBeenCalledWith('/exercises/7', expect.anything())
  })

  it('muestra "sin marca todavía" si nunca se completó', async () => {
    apiFetchMock.mockResolvedValue(detail(null))
    renderCard()
    expect(await screen.findByText(/sin marca todavía/i)).toBeInTheDocument()
  })

  it('muestra el chip de la sesión de hoy solo si se pide', async () => {
    apiFetchMock.mockResolvedValue(detail(null))
    const { unmount } = renderCard()
    await screen.findByText(/sin marca/i)
    expect(screen.queryByText(/en la sesión de hoy/i)).not.toBeInTheDocument()
    unmount()

    renderCard({ inTodaySession: true })
    expect(await screen.findByText(/en la sesión de hoy/i)).toBeInTheDocument()
  })

  it('si falla la carga de la mejor marca, lo avisa pero la tarjeta sigue usable', async () => {
    apiFetchMock.mockRejectedValue(new Error('boom'))
    renderCard()
    expect(
      await screen.findByText(/no se pudo cargar tu mejor marca/i),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /terminé/i })).toBeEnabled()
  })

  it('Terminé envía el bpm elegido, actualiza la mejor marca y avisa', async () => {
    const user = userEvent.setup()
    const onCompleted = vi.fn()
    apiFetchMock.mockResolvedValueOnce(detail(50))
    renderCard({ onCompleted })
    await screen.findByText(/tu mejor/i)

    apiFetchMock.mockResolvedValueOnce({
      id: 1,
      exercise_id: 7,
      completed_at: '2026-01-01T00:00:00Z',
      bpm_logrado: 90,
      instrumento: 'electric',
      best_bpm: 90,
    })
    const slider = screen.getByLabelText(/tempo/i)
    fireEvent.change(slider, { target: { value: '90' } })

    await user.click(screen.getByRole('button', { name: /terminé/i }))

    expect(apiFetchMock).toHaveBeenLastCalledWith(
      '/exercises/7/complete',
      expect.objectContaining({
        method: 'POST',
        body: { bpm_logrado: 90, instrumento: 'electric' },
      }),
    )
    await waitFor(() =>
      expect(screen.getByText(/tu mejor/i)).toHaveTextContent('90 bpm'),
    )
    expect(onCompleted).toHaveBeenCalledWith(
      expect.objectContaining({ best_bpm: 90 }),
    )
  })

  it('si Terminé falla, muestra el error y no avisa', async () => {
    const user = userEvent.setup()
    const onCompleted = vi.fn()
    apiFetchMock.mockResolvedValueOnce(detail(50))
    renderCard({ onCompleted })
    await screen.findByText(/tu mejor/i)

    apiFetchMock.mockRejectedValueOnce(new Error('sin red'))
    await user.click(screen.getByRole('button', { name: /terminé/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/sin red/)
    expect(screen.getByText(/tu mejor/i)).toHaveTextContent('50 bpm')
    expect(onCompleted).not.toHaveBeenCalled()
  })

  it('resalta la misma nota en mástil y tab al reproducir', async () => {
    const user = userEvent.setup()
    apiFetchMock.mockResolvedValue(detail(null))
    const { container } = renderCard()
    await screen.findByText(/sin marca/i)
    expect(activeTabNotes(container)).toHaveLength(0)

    await user.click(screen.getByRole('button', { name: /reproducir/i }))
    audio.clock.advance(1.05) // a 60 bpm, la segunda nota arranca al segundo
    await waitFor(() => expect(activeTabNotes(container)).toHaveLength(1))

    expect(activeTabNotes(container)[0]).toHaveTextContent('7')
    const board = activeBoardNotes(container)
    expect(board).toHaveLength(1)
    expect(board[0]).toHaveAttribute('data-string', '5')
    expect(board[0]).toHaveAttribute('data-fret', '7')
    await user.click(screen.getByRole('button', { name: /pausar/i }))
  })

  it('en modo nota por nota, siguiente y anterior mueven la nota activa', async () => {
    const user = userEvent.setup()
    apiFetchMock.mockResolvedValue(detail(null))
    const { container } = renderCard()
    await screen.findByText(/sin marca/i)

    expect(screen.getByRole('button', { name: /siguiente/i })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: /nota por nota/i }))
    await user.click(screen.getByRole('button', { name: /siguiente/i }))
    expect(activeTabNotes(container)[0]).toHaveTextContent('5')
    await user.click(screen.getByRole('button', { name: /siguiente/i }))
    expect(activeTabNotes(container)[0]).toHaveTextContent('7')

    await user.click(screen.getByRole('button', { name: /anterior/i }))
    expect(activeTabNotes(container)[0]).toHaveTextContent('5')
    expect(activeBoardNotes(container)[0]).toHaveAttribute('data-fret', '5')
  })
})
