import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import type {
  ChordShapeOption,
  SongChartResponse,
  SongDetail,
  StrumPatternEntry,
} from '../../api/songs'
import type { SongChartContent } from '../../songs/types'
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
  audio: [],
  separation_status: 'none',
  sections: [],
}

const content = (name = 'Intro'): SongChartContent => ({
  instrument: 'electric',
  bpm: 82,
  time_signature: '4/4',
  sections: [
    {
      id: 'intro',
      name,
      start_s: 0,
      end_s: 20,
      order: 0,
      chord_source: 'detected',
      chords: [
        { t_s: 0, name: 'Am', shape: ['x', 0, 2, 2, 1, 0], confidence: 0.9 },
        { t_s: 4, name: 'F', shape: [1, 3, 3, 2, 1, 1], confidence: 0.9 },
      ],
      strum: {
        pattern: 'D-DU-UDU',
        accent: [0],
        pattern_id: 'rasgueo-4-folk',
        confidence: 0.8,
      },
    },
    {
      id: 'estrofa',
      name: 'Estrofa',
      start_s: 20,
      end_s: 60,
      order: 1,
      chord_source: 'detected',
      chords: [],
    },
  ],
})

const response = (
  origin: SongChartResponse['origin'],
  body: SongChartContent,
  version = 1,
): SongChartResponse => ({
  song_id: 7,
  instrument: 'electric',
  version,
  origin,
  confidence: 0.7,
  content: body,
  created_at: '2026-10-20T10:00:00Z',
})

const catalog: StrumPatternEntry[] = [
  entry('rasgueo-4-folk', 'Folk clásico', 'D-DU-UDU'),
  entry('rasgueo-4-pop', 'Pop con contratiempo', 'D--UDU-U'),
  { ...entry('rasgueo-3-vals', 'Vals', 'D-D-D-'), beats_per_bar: 3 },
  { ...entry('arpegio-4', 'Arpegio', 'p-i-m-i'), kind: 'arpeggio' },
]

function entry(id: string, name: string, pattern: string): StrumPatternEntry {
  return {
    id,
    name,
    kind: 'strum',
    beats_per_bar: 4,
    style: 'x',
    complexity: 1,
    pattern,
    accent: [0],
    beats_per_cycle: 4,
  }
}

const dm: ChordShapeOption = {
  name: 'Dm',
  chord: 'Dm',
  fallback: null,
  difficulty: 1,
  shape: ['x', 'x', 0, 2, 3, 1],
  barre: null,
}

interface Call {
  method: string
  path: string
  body?: SongChartContent
}

function mockApi(
  initial: SongChartResponse,
  opts: { putStatus?: number } = {},
) {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const path = url.replace('/api/v1', '')
      const method = init?.method ?? 'GET'
      const body = init?.body
        ? (JSON.parse(init.body as string) as SongChartContent)
        : undefined
      calls.push({ method, path, body })
      if (path === '/songs/7') return json(song)
      if (path === '/strum-patterns') return json(catalog)
      if (path.startsWith('/chords/shapes?name=Dm')) return json([dm])
      if (path.startsWith('/chords/shapes')) return json([], 422)
      if (path === '/songs/7/chart?instrument=electric' && method === 'GET')
        return json(initial)
      if (path === '/songs/7/chart?instrument=electric' && method === 'PUT') {
        if (opts.putStatus)
          return json({ detail: 'Chart inválido' }, opts.putStatus)
        return json(response('user', body!, 2))
      }
      if (path === '/songs/7/chart/user?instrument=electric')
        return json(response('auto', content(), 3))
      return json({ detail: 'no existe' }, 404)
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

async function openEditor() {
  const user = userEvent.setup()
  renderScreen()
  await user.click(await screen.findByRole('button', { name: 'Eléctrica' }))
  await user.click(
    await screen.findByRole('button', { name: 'Editar sección' }),
  )
  return {
    user,
    form: await screen.findByRole('form', { name: /Editar sección/ }),
  }
}

afterEach(() => vi.unstubAllGlobals())

describe('edición de una sección', () => {
  it('no muestra "editado por vos" sobre la versión automática', async () => {
    mockApi(response('auto', content()))
    await openEditor()
    expect(screen.queryByText('Editado por vos')).not.toBeInTheDocument()
  })

  it('renombra la sección y guarda el chart completo', async () => {
    const calls = mockApi(response('auto', content()))
    const { user, form } = await openEditor()
    const name = within(form).getByLabelText('Nombre')
    await user.clear(name)
    await user.type(name, 'Entrada')
    await user.click(within(form).getByRole('button', { name: 'Guardar' }))

    const put = calls.find((c) => c.method === 'PUT')
    expect(put?.body?.sections.map((s) => s.name)).toEqual([
      'Entrada',
      'Estrofa',
    ])
    expect(put?.body?.sections[0]?.chord_source).toBe('detected')
    expect(await screen.findByText('Editado por vos')).toBeInTheDocument()
    expect(
      screen.getByRole('article', { name: 'Sección Entrada' }),
    ).toBeInTheDocument()
  })

  it('cambia un acorde y recalcula la forma desde el diccionario', async () => {
    const calls = mockApi(response('auto', content()))
    const { user, form } = await openEditor()
    const chord = within(form).getByLabelText('Acorde 1')
    await user.clear(chord)
    await user.type(chord, 'Dm')
    await user.click(within(form).getByRole('button', { name: 'Guardar' }))

    await screen.findByText('Editado por vos')
    const sent = calls.find((c) => c.method === 'PUT')?.body?.sections[0]
    expect(sent?.chords?.[0]).toMatchObject({
      t_s: 0,
      name: 'Dm',
      shape: ['x', 'x', 0, 2, 3, 1],
      confidence: 1,
    })
    expect(sent?.chords?.[1]?.name).toBe('F')
    expect(sent?.chord_source).toBe('user')
    expect(calls.map((c) => c.path)).toContain('/chords/shapes?name=Dm')
  })

  it('avisa si el acorde no existe y no guarda', async () => {
    const calls = mockApi(response('auto', content()))
    const { user, form } = await openEditor()
    const chord = within(form).getByLabelText('Acorde 1')
    await user.clear(chord)
    await user.type(chord, 'Zz')
    await user.click(within(form).getByRole('button', { name: 'Guardar' }))
    expect(await within(form).findByRole('alert')).toHaveTextContent(
      'No encontré el acorde "Zz".',
    )
    expect(calls.some((c) => c.method === 'PUT')).toBe(false)
  })

  it('mueve los límites de la sección', async () => {
    const calls = mockApi(response('auto', content()))
    const { user, form } = await openEditor()
    const end = within(form).getByLabelText('Fin (s)')
    await user.clear(end)
    await user.type(end, '18.5')
    await user.click(within(form).getByRole('button', { name: 'Guardar' }))
    await screen.findByText('Editado por vos')
    expect(
      calls.find((c) => c.method === 'PUT')?.body?.sections[0]?.end_s,
    ).toBe(18.5)
  })

  it('rechaza límites que pisan a la sección vecina sin llamar a la API', async () => {
    const calls = mockApi(response('auto', content()))
    const { user, form } = await openEditor()
    const end = within(form).getByLabelText('Fin (s)')
    await user.clear(end)
    await user.type(end, '25')
    await user.click(within(form).getByRole('button', { name: 'Guardar' }))
    expect(await within(form).findByRole('alert')).toHaveTextContent(
      'Se pisa con la sección Estrofa.',
    )
    expect(calls.some((c) => c.method === 'PUT')).toBe(false)
  })

  it('cambia el rasgueo por uno del catálogo con el mismo compás', async () => {
    const calls = mockApi(response('auto', content()))
    const { user, form } = await openEditor()
    const select = await within(form).findByLabelText('Patrón de rasgueo')
    const labels = within(select)
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect(labels).toEqual([
      'Dejar como está',
      'Folk clásico (D-DU-UDU)',
      'Pop con contratiempo (D--UDU-U)',
    ])
    await user.selectOptions(select, 'rasgueo-4-pop')
    await user.click(within(form).getByRole('button', { name: 'Guardar' }))
    await screen.findByText('Editado por vos')
    expect(
      calls.find((c) => c.method === 'PUT')?.body?.sections[0]?.strum,
    ).toMatchObject({ pattern_id: 'rasgueo-4-pop', pattern: 'D--UDU-U' })
    expect(
      await screen.findByRole('group', { name: 'Rasgueo D--UDU-U' }),
    ).toBeInTheDocument()
  })

  it('muestra el error del servidor y deja seguir editando', async () => {
    mockApi(response('auto', content()), { putStatus: 422 })
    const { user, form } = await openEditor()
    await user.click(within(form).getByRole('button', { name: 'Guardar' }))
    expect(await within(form).findByRole('alert')).toHaveTextContent(
      'Chart inválido',
    )
    expect(within(form).getByRole('button', { name: 'Guardar' })).toBeEnabled()
  })

  it('cancelar vuelve a la vista sin llamar a la API', async () => {
    const calls = mockApi(response('auto', content()))
    const { user, form } = await openEditor()
    await user.click(within(form).getByRole('button', { name: 'Cancelar' }))
    expect(
      screen.getByRole('article', { name: 'Sección Intro' }),
    ).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'PUT')).toBe(false)
  })
})

describe('versión de usuario', () => {
  it('muestra "editado por vos" cuando el chart vigente es del usuario', async () => {
    mockApi(response('user', content('Entrada'), 2))
    const user = userEvent.setup()
    renderScreen()
    await user.click(await screen.findByRole('button', { name: 'Eléctrica' }))
    expect(await screen.findByText('Editado por vos')).toBeInTheDocument()
  })

  it('vuelve a la automática después de confirmar', async () => {
    const calls = mockApi(response('user', content('Entrada'), 2))
    const user = userEvent.setup()
    renderScreen()
    await user.click(await screen.findByRole('button', { name: 'Eléctrica' }))
    await user.click(
      await screen.findByRole('button', { name: 'Volver a la automática' }),
    )
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
    await user.click(screen.getByRole('button', { name: 'Sí, volver' }))

    expect(
      await screen.findByRole('article', { name: 'Sección Intro' }),
    ).toBeInTheDocument()
    expect(screen.queryByText('Editado por vos')).not.toBeInTheDocument()
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: 'DELETE',
        path: '/songs/7/chart/user?instrument=electric',
      }),
    )
  })

  it('"No" deja todo como estaba', async () => {
    const calls = mockApi(response('user', content('Entrada'), 2))
    const user = userEvent.setup()
    renderScreen()
    await user.click(await screen.findByRole('button', { name: 'Eléctrica' }))
    await user.click(
      await screen.findByRole('button', { name: 'Volver a la automática' }),
    )
    await user.click(screen.getByRole('button', { name: 'No' }))
    expect(screen.getByText('Editado por vos')).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
  })
})
