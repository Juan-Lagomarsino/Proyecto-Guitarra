import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import type { SongDetail, SongChartResponse } from '../../api/songs'
import type { ChartSection, SongChartContent } from '../../songs/types'
import { SongScreen } from './SongScreen'

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
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
  sections: [
    {
      id: 3,
      slug: 'puente',
      name: 'Puente viejo',
      start_s: 0,
      end_s: 5,
      position: -3,
      stale: true,
    },
  ],
}

const section = (over: Partial<ChartSection>): ChartSection => ({
  id: 'intro',
  name: 'Intro',
  start_s: 0,
  end_s: 20,
  order: 0,
  chord_source: 'detected',
  chords: [
    {
      t_s: 0,
      name: 'Am',
      shape: ['x', 0, 2, 2, 1, 0],
      confidence: 0.9,
    },
    {
      t_s: 4,
      name: 'F',
      shape: [1, 3, 3, 2, 1, 1],
      barre: { fret: 1, from_string: 6, to_string: 1 },
      confidence: 0.3,
    },
  ],
  strum: {
    pattern: 'D-DU-UDU',
    accent: [0],
    pattern_id: 'p1',
    confidence: 0.8,
  },
  ...over,
})

const chart = (
  instrument: 'classical' | 'electric',
  sections: ChartSection[],
  capo = 0,
): SongChartResponse => {
  const content: SongChartContent = {
    instrument,
    bpm: 81.6,
    key: { tonic: 'D', mode: 'minor', confidence: 0.9 },
    capo,
    sections: sections as SongChartContent['sections'],
  }
  return {
    song_id: 7,
    instrument,
    version: 1,
    origin: 'auto',
    confidence: 0.7,
    content,
    created_at: '2026-10-20T10:00:00Z',
  }
}

const verse = section({
  id: 'estrofa',
  name: 'Estrofa',
  start_s: 20,
  end_s: 60,
  order: 1,
  chord_source: 'cifraclub',
  chords: [{ t_s: 20, name: 'G', shape: [3, 2, 0, 0, 0, 3], confidence: 0.95 }],
})

const classical = chart('classical', [
  section({
    arpeggio: { pattern_id: 'a1', pattern: 'p-i-m-a-m-i', confidence: 0.9 },
  }),
  verse,
])

const mockApi = (charts: Record<string, SongChartResponse | undefined>) => {
  const calls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const path = url.replace('/api/v1', '')
      calls.push(path)
      if (path === '/songs/7') return json(song)
      if (path === '/songs/7/exercises') return json([])
      const match = /^\/songs\/7\/chart\?instrument=(\w+)$/.exec(path)
      const found = match ? charts[match[1]] : undefined
      return found ? json(found) : json({ detail: 'sin chart' }, 404)
    }),
  )
  return calls
}

const renderScreen = () =>
  render(
    <MemoryRouter initialEntries={['/explorar/canciones/7']}>
      <Routes>
        <Route path="explorar/canciones/:id" element={<SongScreen />} />
      </Routes>
    </MemoryRouter>,
  )

afterEach(() => vi.unstubAllGlobals())

describe('SongScreen', () => {
  it('muestra la cabecera con título, artista, BPM, tonalidad y capo', async () => {
    mockApi({ classical: chart('classical', [section({})], 2) })
    renderScreen()
    expect(
      await screen.findByRole('heading', { name: 'Come Together' }),
    ).toBeInTheDocument()
    expect(screen.getByText('The Beatles')).toBeInTheDocument()
    expect(await screen.findByText('82')).toBeInTheDocument()
    expect(screen.getByText('D menor')).toBeInTheDocument()
    expect(screen.getByText('Capo en 2')).toBeInTheDocument()
  })

  it('arranca en clásica y pide el chart de ese instrumento', async () => {
    const calls = mockApi({ classical })
    renderScreen()
    await screen.findByRole('group', { name: 'Arpegio p-i-m-a-m-i' })
    expect(calls).toContain('/songs/7/chart?instrument=classical')
    expect(screen.getByRole('button', { name: 'Clásica' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('cambia a eléctrica y muestra el rasgueo', async () => {
    const user = userEvent.setup()
    mockApi({ classical, electric: chart('electric', [section({})]) })
    renderScreen()
    await screen.findByRole('group', { name: 'Arpegio p-i-m-a-m-i' })
    await user.click(screen.getByRole('button', { name: 'Eléctrica' }))
    expect(
      await screen.findByRole('group', { name: 'Rasgueo D-DU-UDU' }),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Arpegio/)).not.toBeInTheDocument()
  })

  it('en clásica sin arpegio cae al rasgueo', async () => {
    mockApi({ classical: chart('classical', [section({})]) })
    renderScreen()
    expect(
      await screen.findByRole('group', { name: 'Rasgueo D-DU-UDU' }),
    ).toBeInTheDocument()
  })

  it('la línea de tiempo cambia de sección y marca Cifra Club', async () => {
    const user = userEvent.setup()
    mockApi({ classical })
    renderScreen()
    await screen.findByRole('article', { name: 'Sección Intro' })
    expect(screen.queryByText('Acordes de Cifra Club')).not.toBeInTheDocument()

    const timeline = screen.getByRole('list', {
      name: 'Secciones de la canción',
    })
    await user.click(within(timeline).getByRole('button', { name: /Estrofa/ }))

    const detail = screen.getByRole('article', { name: 'Sección Estrofa' })
    expect(within(detail).getByText('Acordes de Cifra Club')).toBeVisible()
    expect(within(detail).getByRole('img', { name: /Acorde G:/ })).toBeVisible()
  })

  it('muestra un diagrama por acorde distinto y marca la baja confianza', async () => {
    mockApi({ classical })
    renderScreen()
    const diagrams = await screen.findByRole('list', {
      name: 'Diagramas de acordes',
    })
    expect(within(diagrams).getAllByRole('img')).toHaveLength(2)
    const items = within(diagrams).getAllByRole('listitem')
    expect(items[0]).toHaveAttribute('data-confidence', 'ok')
    expect(items[1]).toHaveAttribute('data-confidence', 'low')
    expect(screen.getByText(/Baja confianza/)).toBeInTheDocument()
  })

  it('lista las secciones anteriores aparte, fuera de la línea de tiempo', async () => {
    mockApi({ classical })
    renderScreen()
    await screen.findByRole('article', { name: 'Sección Intro' })
    const stale = await screen.findByRole('region', {
      name: 'Secciones anteriores',
    })
    expect(within(stale).getByText('Puente viejo')).toBeInTheDocument()
    const timeline = screen.getByRole('list', {
      name: 'Secciones de la canción',
    })
    expect(within(timeline).queryByText('Puente viejo')).toBeNull()
  })

  it('avisa si todavía no hay chart de ese instrumento', async () => {
    mockApi({ classical })
    const user = userEvent.setup()
    renderScreen()
    await screen.findByRole('article', { name: 'Sección Intro' })
    await user.click(screen.getByRole('button', { name: 'Eléctrica' }))
    expect(
      await screen.findByText(/no hay acordes de guitarra eléctrica/),
    ).toBeInTheDocument()
  })

  it('muestra el error si la canción no carga', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => json({ detail: 'no existe' }, 404)),
    )
    renderScreen()
    expect(await screen.findByRole('alert')).toHaveTextContent(/No se pudo/)
  })

  it('al guardar la cifra recarga el detalle y muestra que se reanaliza', async () => {
    const user = userEvent.setup()
    let detail = song
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        const path = url.replace('/api/v1', '')
        if (path === '/songs/7/cifra' && init?.method === 'PUT') {
          detail = { ...song, analysis_status: 'queued', has_cifra: true }
          return json({ ...detail, reanalysis_queued: true })
        }
        if (path === '/songs/7') return json(detail)
        return json({ detail: 'sin chart' }, 404)
      }),
    )
    renderScreen()
    await screen.findByRole('heading', { name: 'Come Together' })
    expect(screen.queryByText(/Reanalizando/)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Cargar cifra' }))
    await user.type(screen.getByLabelText('Texto de la cifra'), 'Am')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(
      await screen.findByText('Reanalizando la canción…'),
    ).toBeInTheDocument()
  })
})
