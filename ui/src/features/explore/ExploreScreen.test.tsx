import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import type { SongDetail, SongSummary } from '../../api/songs'
import { ExploreScreen } from './ExploreScreen'

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

const summary = (over: Partial<SongSummary> = {}): SongSummary => ({
  id: 1,
  title: 'Come Together',
  artist: 'The Beatles',
  source: 'youtube',
  analysis_status: 'ready',
  current_step: null,
  bpm: 82,
  key: 'Dm',
  created_at: '2026-10-20T10:00:00Z',
  url: 'https://youtu.be/abc',
  error: null,
  ...over,
})

const detail = (over: Partial<SongDetail> = {}): SongDetail => ({
  ...summary(),
  duration_s: null,
  year: null,
  has_cifra: false,
  cifra_url: null,
  audio: [],
  separation_status: 'none',
  sections: [],
  ...over,
})

interface Api {
  songs: SongSummary[]
  post?: { status: number; body: unknown }
  reanalyze?: { status: number; body: unknown }
  calls: { method: string; path: string; body?: unknown }[]
}

const mockApi = (initial: Partial<Api> = {}) => {
  const api: Api = { songs: [], calls: [], ...initial }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const path = url.replace('/api/v1', '')
      const method = init?.method ?? 'GET'
      const body = init?.body ? JSON.parse(init.body as string) : undefined
      api.calls.push({ method, path, body })
      if (method === 'POST' && path === '/songs') {
        const { status, body: out } = api.post!
        return json(out, status)
      }
      if (method === 'POST') {
        const { status, body: out } = api.reanalyze ?? { status: 202, body: {} }
        return json(out, status)
      }
      if (path === '/songs') return json(api.songs)
      return json({ detail: 'ruta no mockeada' }, 404)
    }),
  )
  return api
}

const flush = () => act(() => vi.advanceTimersByTimeAsync(0))
const tick = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms))

const renderScreen = async () => {
  render(
    <MemoryRouter>
      <ExploreScreen />
    </MemoryRouter>,
  )
  await flush()
}

const listCalls = (api: Api) =>
  api.calls.filter((c) => c.method === 'GET' && c.path === '/songs').length

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('ExploreScreen - biblioteca', () => {
  it('muestra el estado vacío con instrucciones', async () => {
    mockApi()
    await renderScreen()
    expect(screen.getByText(/todavía no tenés canciones/i)).toBeInTheDocument()
    expect(screen.getByText(/pegá un link/i)).toBeInTheDocument()
  })

  it('muestra un error si no carga la biblioteca', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => json({ detail: 'caída' }, 500)),
    )
    await renderScreen()
    expect(screen.getByRole('alert')).toHaveTextContent(/no se pudo cargar/i)
  })

  it('canción lista: título, artista, bpm, tonalidad y link a su vista', async () => {
    mockApi({ songs: [summary()] })
    await renderScreen()
    const link = screen.getByRole('link', { name: /come together/i })
    expect(link).toHaveAttribute('href', '/explorar/canciones/1')
    const row = screen.getByRole('listitem')
    expect(within(row).getByText('The Beatles')).toBeInTheDocument()
    expect(within(row).getByText('Lista')).toBeInTheDocument()
    expect(within(row).getByText(/82 bpm/i)).toBeInTheDocument()
    expect(within(row).getByText('Dm')).toBeInTheDocument()
  })

  it('en cola: chip y sin link', async () => {
    mockApi({
      songs: [
        summary({
          title: 'X',
          analysis_status: 'queued',
          bpm: null,
          key: null,
        }),
      ],
    })
    await renderScreen()
    expect(screen.getByText('En cola')).toBeInTheDocument()
    expect(screen.queryByRole('link')).toBeNull()
  })

  it('procesando: traduce el paso actual', async () => {
    mockApi({
      songs: [
        summary({ analysis_status: 'processing', current_step: 'tempo' }),
      ],
    })
    await renderScreen()
    expect(screen.getByText(/detectando el tempo/i)).toBeInTheDocument()
  })

  it('paso desconocido: se muestra tal cual', async () => {
    mockApi({
      songs: [
        summary({ analysis_status: 'processing', current_step: 'raro_x' }),
      ],
    })
    await renderScreen()
    expect(screen.getByText(/raro_x/)).toBeInTheDocument()
  })

  it('sin título: "Analizando…" y la URL', async () => {
    mockApi({
      songs: [
        summary({
          title: null,
          artist: null,
          analysis_status: 'queued',
          bpm: null,
          key: null,
          url: 'https://youtu.be/zzz',
        }),
      ],
    })
    await renderScreen()
    expect(screen.getByText('Analizando…')).toBeInTheDocument()
    expect(screen.getByText('https://youtu.be/zzz')).toBeInTheDocument()
  })

  it('con error: muestra el error tal cual y reintenta', async () => {
    const api = mockApi({
      songs: [
        summary({
          analysis_status: 'error',
          bpm: null,
          key: null,
          error: 'Falta SPOTIFY_CLIENT_ID',
        }),
      ],
    })
    await renderScreen()
    expect(screen.getByText('Falta SPOTIFY_CLIENT_ID')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /reintentar/i }))
    await flush()
    expect(api.calls).toContainEqual({
      method: 'POST',
      path: '/songs/1/reanalyze',
      body: undefined,
    })
  })

  it('si reintentar da 409 lo avisa', async () => {
    mockApi({
      songs: [summary({ analysis_status: 'error' })],
      reanalyze: {
        status: 409,
        body: { detail: 'Ya hay un análisis en curso' },
      },
    })
    await renderScreen()
    await userEvent.click(screen.getByRole('button', { name: /reintentar/i }))
    await flush()
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Ya hay un análisis en curso',
    )
  })
})

describe('ExploreScreen - polling', () => {
  it('refresca cada 3 s mientras hay una canción activa y se detiene al terminar', async () => {
    const api = mockApi({
      songs: [
        summary({ analysis_status: 'processing', current_step: 'tempo' }),
      ],
    })
    await renderScreen()
    expect(listCalls(api)).toBe(1)

    await tick(3000)
    expect(listCalls(api)).toBe(2)

    api.songs = [summary({ analysis_status: 'ready' })]
    await tick(3000)
    expect(listCalls(api)).toBe(3)
    expect(screen.getByText('Lista')).toBeInTheDocument()

    await tick(10000)
    expect(listCalls(api)).toBe(3)
  })

  it('no hace polling si no hay nada activo', async () => {
    const api = mockApi({ songs: [summary()] })
    await renderScreen()
    await tick(10000)
    expect(listCalls(api)).toBe(1)
  })

  it('se detiene al desmontar', async () => {
    const api = mockApi({
      songs: [summary({ analysis_status: 'queued' })],
    })
    const { unmount } = render(
      <MemoryRouter>
        <ExploreScreen />
      </MemoryRouter>,
    )
    await flush()
    unmount()
    await tick(10000)
    expect(listCalls(api)).toBe(1)
  })
})

describe('ExploreScreen - alta', () => {
  it('alta por link: llama a la API y la canción aparece arriba', async () => {
    const api = mockApi({
      songs: [summary({ id: 1 })],
      post: {
        status: 201,
        body: detail({
          id: 2,
          title: null,
          artist: null,
          analysis_status: 'queued',
        }),
      },
    })
    await renderScreen()
    await userEvent.type(
      screen.getByLabelText(/link de youtube o spotify/i),
      'https://youtu.be/abc',
    )
    api.songs = [
      summary({ id: 2, title: 'Nueva', analysis_status: 'queued' }),
      summary({ id: 1 }),
    ]
    await userEvent.click(screen.getByRole('button', { name: /agregar/i }))
    await flush()

    expect(api.calls).toContainEqual({
      method: 'POST',
      path: '/songs',
      body: { url: 'https://youtu.be/abc' },
    })
    const rows = screen.getAllByRole('listitem')
    expect(within(rows[0]).getByText('Nueva')).toBeInTheDocument()
    expect(screen.queryByText(/ya la tenías/i)).toBeNull()
  })

  it('alta por nombre: manda título y artista', async () => {
    const api = mockApi({
      post: { status: 201, body: detail({ id: 3 }) },
    })
    await renderScreen()
    await userEvent.click(
      screen.getByRole('button', { name: /buscar por nombre/i }),
    )
    await userEvent.type(screen.getByLabelText('Título'), 'Blackbird')
    await userEvent.type(screen.getByLabelText('Artista'), 'The Beatles')
    await userEvent.click(screen.getByRole('button', { name: /agregar/i }))
    await flush()
    expect(api.calls).toContainEqual({
      method: 'POST',
      path: '/songs',
      body: { title: 'Blackbird', artist: 'The Beatles' },
    })
  })

  it('exige título y artista en el modo por nombre', async () => {
    const api = mockApi()
    await renderScreen()
    await userEvent.click(
      screen.getByRole('button', { name: /buscar por nombre/i }),
    )
    await userEvent.type(screen.getByLabelText('Título'), 'Blackbird')
    await userEvent.click(screen.getByRole('button', { name: /agregar/i }))
    expect(screen.getByRole('alert')).toHaveTextContent(/título y el artista/i)
    expect(api.calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('no manda a la API un texto que no parece link', async () => {
    const api = mockApi()
    await renderScreen()
    await userEvent.type(
      screen.getByLabelText(/link de youtube o spotify/i),
      'hola',
    )
    await userEvent.click(screen.getByRole('button', { name: /agregar/i }))
    expect(screen.getByRole('alert')).toHaveTextContent(
      /no parece un link de youtube o spotify/i,
    )
    expect(api.calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('muestra legible el 422 de la API', async () => {
    mockApi({
      post: { status: 422, body: { detail: 'Link de YouTube no reconocido' } },
    })
    await renderScreen()
    await userEvent.type(
      screen.getByLabelText(/link de youtube o spotify/i),
      'https://youtu.be/abc',
    )
    await userEvent.click(screen.getByRole('button', { name: /agregar/i }))
    await flush()
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Link de YouTube no reconocido',
    )
  })

  it('"Ya la tenías" (200) avisa y resalta la fila existente', async () => {
    mockApi({
      songs: [summary({ id: 1 }), summary({ id: 2, title: 'Otra' })],
      post: { status: 200, body: detail({ id: 2 }) },
    })
    await renderScreen()
    await userEvent.type(
      screen.getByLabelText(/link de youtube o spotify/i),
      'https://youtu.be/abc',
    )
    await userEvent.click(screen.getByRole('button', { name: /agregar/i }))
    await flush()
    expect(screen.getByRole('status')).toHaveTextContent(/ya la tenías/i)
    const rows = screen.getAllByRole('listitem')
    expect(rows[1]).toHaveAttribute('data-highlighted', 'true')
    expect(rows[0]).not.toHaveAttribute('data-highlighted', 'true')
  })
})
