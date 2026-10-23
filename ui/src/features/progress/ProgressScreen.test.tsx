import { render, screen, waitFor } from '@testing-library/react'
import { ProgressScreen } from './ProgressScreen'
import { buildWeeks, heatLevel, yearRange } from './heatGrid'

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

const summary = {
  current_streak: 3,
  max_streak: 7,
  practiced_days: 12,
  levels: [
    {
      level_id: 1,
      slug: 'n1',
      position: 1,
      name: 'Primeros pasos',
      completed: 2,
      total: 5,
    },
  ],
}

const mockApi = (
  sum: unknown = summary,
  days: { date: string; count: number }[] = [],
) => {
  const fetchMock = vi.fn(async (url: string) =>
    url.includes('/progress/summary') ? json(sum) : json({ days }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('heatLevel', () => {
  it.each([
    [0, 0],
    [1, 1],
    [2, 2],
    [3, 3],
    [4, 3],
    [5, 4],
    [20, 4],
  ])('cantidad %i -> nivel %i', (count, level) => {
    expect(heatLevel(count)).toBe(level)
  })
})

describe('buildWeeks', () => {
  it('arma columnas lunes a domingo con nulls fuera de rango', () => {
    // 2026-10-21 es miércoles
    const weeks = buildWeeks('2026-10-21', '2026-10-24', [
      { date: '2026-10-22', count: 2 },
    ])
    expect(weeks).toHaveLength(1)
    expect(weeks[0].cells[0]).toBeNull()
    expect(weeks[0].cells[2]).toMatchObject({ date: '2026-10-21', level: 0 })
    expect(weeks[0].cells[3]).toMatchObject({ date: '2026-10-22', level: 2 })
    expect(weeks[0].cells[6]).toBeNull()
  })
})

describe('ProgressScreen', () => {
  it('muestra rachas, heatmap con intensidad y avance por nivel', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 9, 23, 12))
    mockApi(summary, [
      { date: '2026-10-20', count: 1 },
      { date: '2026-10-21', count: 6 },
    ])
    render(<ProgressScreen />)
    expect(await screen.findByText('3 días')).toBeInTheDocument()
    expect(screen.getByText('7 días')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('Primeros pasos')).toBeInTheDocument()
    expect(screen.getByText('2/5')).toBeInTheDocument()
    expect(screen.getByLabelText('20/10/2026: 1 ejercicio')).toHaveAttribute(
      'data-level',
      '1',
    )
    expect(screen.getByLabelText('21/10/2026: 6 ejercicios')).toHaveAttribute(
      'data-level',
      '4',
    )
    expect(screen.getByLabelText('22/10/2026: sin ejercicios')).toHaveAttribute(
      'data-level',
      '0',
    )
    expect(screen.getAllByText('oct').length).toBeGreaterThan(0)
  })

  it('pide el calendario de un año hasta hoy', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 9, 23, 12))
    const fetchMock = mockApi()
    expect(yearRange(new Date())).toEqual({
      from: '2025-10-23',
      to: '2026-10-23',
    })
    render(<ProgressScreen />)
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/v1/progress/calendar?from=2025-10-23&to=2026-10-23',
        expect.anything(),
      ),
    )
    await screen.findByText('Avance por nivel')
  })

  it('muestra un estado vacío amable sin práctica', async () => {
    mockApi({ ...summary, current_streak: 0, max_streak: 0, practiced_days: 0 })
    render(<ProgressScreen />)
    expect(
      await screen.findByText(/Todavía no practicaste/),
    ).toBeInTheDocument()
  })

  it('avisa si falla la carga', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => json({ detail: 'boom' }, 500)),
    )
    render(<ProgressScreen />)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No pudimos cargar tu progreso',
    )
  })
})
