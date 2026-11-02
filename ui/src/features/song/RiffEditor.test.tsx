import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { SongChartResponse, SongDetail } from '../../api/songs'
import type { SongChartContent } from '../../songs/types'
import css from './riffEditor.css?raw'
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
  bpm: 60,
  key: 'Dm',
  created_at: '2026-10-20T10:00:00Z',
  url: null,
  error: null,
  duration_s: 60,
  year: 1969,
  has_cifra: false,
  cifra_url: null,
  audio: [],
  separation_status: 'none',
  sections: [],
}

// bpm 60 y sin grilla: la sección Intro dura 8 beats (8 s).
const content = (withRiff = true): SongChartContent => ({
  instrument: 'electric',
  bpm: 60,
  time_signature: '4/4',
  sections: [
    {
      id: 'intro',
      name: 'Intro',
      start_s: 0,
      end_s: 8,
      order: 0,
      chord_source: 'detected',
      chords: [],
      riff: withRiff
        ? {
            bpm: 60,
            events: [
              { t: 0, dur: 1, string: 5, fret: 3, confidence: 0.9 },
              { t: 1, dur: 1, string: 4, fret: 5, confidence: 0.4 },
              { t: 2, dur: 2, string: 3, fret: 7, confidence: 0.8 },
            ],
          }
        : null,
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
  riff_sources: {
    intro: body.sections[0].riff
      ? origin === 'user'
        ? 'usuario'
        : 'auto'
      : null,
  },
  created_at: '2026-10-20T10:00:00Z',
})

interface Call {
  method: string
  path: string
  body?: SongChartContent
}

function mockApi(
  initial: SongChartResponse,
  opts: { putError?: { status: number; body: unknown } } = {},
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
      if (path === '/strum-patterns') return json([])
      if (path === '/songs/7/chart?instrument=electric' && method === 'GET')
        return json(initial)
      if (path === '/songs/7/chart?instrument=electric' && method === 'PUT') {
        if (opts.putError) return json(opts.putError.body, opts.putError.status)
        return json(response('user', body!, 2))
      }
      if (path === '/songs/7/chart/user?instrument=electric')
        return json(response('auto', content(), 3))
      return json({ detail: 'no existe' }, 404)
    }),
  )
  return calls
}

async function openRiffEditor(buttonName = 'Editar tab') {
  const user = userEvent.setup()
  render(
    <MemoryRouter initialEntries={['/explorar/canciones/7']}>
      <Routes>
        <Route path="explorar/canciones/:id" element={<SongScreen />} />
      </Routes>
    </MemoryRouter>,
  )
  await user.click(await screen.findByRole('button', { name: 'Eléctrica' }))
  await user.click(await screen.findByRole('button', { name: buttonName }))
  const editor = await screen.findByRole('region', { name: /Editar riff/ })
  return { user, editor }
}

const note = (t: number, string: number, fret: number) =>
  `Tiempo ${t}, cuerda ${string}, traste ${fret}`

const savedRiff = (calls: Call[]) =>
  calls.find((c) => c.method === 'PUT')?.body?.sections[0].riff

afterEach(() => vi.unstubAllGlobals())

describe('editor de tab del riff', () => {
  it('cambia un traste y guarda el riff nuevo en el PUT, con la nota como del usuario', async () => {
    const calls = mockApi(response('auto', content()))
    const { user, editor } = await openRiffEditor()
    await user.click(
      within(editor).getByRole('button', { name: note(0, 5, 3) }),
    )
    await user.selectOptions(within(editor).getByLabelText('Traste'), '7')
    await user.click(within(editor).getByRole('button', { name: 'Guardar' }))

    const riff = savedRiff(calls)
    expect(riff?.bpm).toBe(60)
    expect(riff?.events).toEqual([
      { t: 0, dur: 1, string: 5, fret: 7 },
      { t: 1, dur: 1, string: 4, fret: 5, confidence: 0.4 },
      { t: 2, dur: 2, string: 3, fret: 7, confidence: 0.8 },
    ])
    expect(await screen.findByText('Riff editado por vos')).toBeTruthy()
    expect(
      screen.queryByRole('region', { name: /Editar riff/ }),
    ).not.toBeInTheDocument()
  })

  it('no muestra "editado por vos" sobre el riff automático', async () => {
    mockApi(response('auto', content()))
    await openRiffEditor()
    expect(screen.queryByText('Riff editado por vos')).not.toBeInTheDocument()
  })

  it('cambiar de cuerda conserva la altura (recalcula el traste)', async () => {
    const calls = mockApi(response('auto', content()))
    const { user, editor } = await openRiffEditor()
    await user.click(
      within(editor).getByRole('button', { name: note(0, 5, 3) }),
    )
    await user.selectOptions(within(editor).getByLabelText('Cuerda'), '6')
    expect(
      within(editor).getByRole('button', { name: note(0, 6, 8) }),
    ).toBeTruthy()
    await user.click(within(editor).getByRole('button', { name: 'Guardar' }))
    expect(savedRiff(calls)?.events?.[0]).toMatchObject({ string: 6, fret: 8 })
  })

  it('avisa si la altura no existe en esa cuerda y no cambia', async () => {
    mockApi(response('auto', content()))
    const { user, editor } = await openRiffEditor()
    await user.click(
      within(editor).getByRole('button', { name: note(0, 5, 3) }),
    )
    await user.selectOptions(within(editor).getByLabelText('Cuerda'), '1')
    expect(within(editor).getByRole('status').textContent).toMatch(
      /no existe en la cuerda 1/,
    )
    expect(
      within(editor).getByRole('button', { name: note(0, 5, 3) }),
    ).toBeTruthy()
  })

  it('con "traste libre" cambia la cuerda y deja el traste', async () => {
    mockApi(response('auto', content()))
    const { user, editor } = await openRiffEditor()
    await user.click(
      within(editor).getByRole('button', { name: note(0, 5, 3) }),
    )
    await user.click(within(editor).getByLabelText(/traste libre/))
    await user.selectOptions(within(editor).getByLabelText('Cuerda'), '2')
    expect(
      within(editor).getByRole('button', { name: note(0, 2, 3) }),
    ).toBeTruthy()
  })

  it('cambia técnica (con bend) y duración', async () => {
    const calls = mockApi(response('auto', content()))
    const { user, editor } = await openRiffEditor()
    await user.click(
      within(editor).getByRole('button', { name: note(1, 4, 5) }),
    )
    await user.selectOptions(within(editor).getByLabelText('Técnica'), 'b')
    await user.selectOptions(
      within(editor).getByLabelText('Bend (semitonos)'),
      '2',
    )
    await user.selectOptions(
      within(editor).getByLabelText('Duración'),
      '1/2 beat',
    )
    await user.click(within(editor).getByRole('button', { name: 'Guardar' }))
    expect(savedRiff(calls)?.events?.[1]).toEqual({
      t: 1,
      dur: 0.5,
      string: 4,
      fret: 5,
      technique: 'b',
      bend: 2,
    })
  })

  it('deshace los cambios', async () => {
    mockApi(response('auto', content()))
    const { user, editor } = await openRiffEditor()
    const undoButton = within(editor).getByRole('button', { name: 'Deshacer' })
    expect(undoButton).toBeDisabled()
    await user.click(
      within(editor).getByRole('button', { name: note(0, 5, 3) }),
    )
    await user.selectOptions(within(editor).getByLabelText('Traste'), '9')
    expect(
      within(editor).getByRole('button', { name: note(0, 5, 9) }),
    ).toBeTruthy()
    await user.click(undoButton)
    expect(
      within(editor).getByRole('button', { name: note(0, 5, 3) }),
    ).toBeTruthy()
    expect(undoButton).toBeDisabled()
  })

  it('agrega y borra notas', async () => {
    const calls = mockApi(response('auto', content()))
    const { user, editor } = await openRiffEditor()
    const add = within(editor).getByRole('group', { name: 'Agregar nota' })
    const time = within(add).getByLabelText(/Tiempo/)
    await user.clear(time)
    await user.type(time, '4')
    await user.selectOptions(within(add).getByLabelText('Cuerda nueva'), '2')
    await user.selectOptions(within(add).getByLabelText('Traste nuevo'), '12')
    await user.click(within(add).getByRole('button', { name: 'Agregar nota' }))
    expect(
      within(editor).getByRole('button', { name: note(4, 2, 12) }),
    ).toBeTruthy()

    await user.click(
      within(editor).getByRole('button', { name: note(1, 4, 5) }),
    )
    await user.click(
      within(editor).getByRole('button', { name: 'Borrar nota' }),
    )
    expect(
      within(editor).queryByRole('button', { name: note(1, 4, 5) }),
    ).not.toBeInTheDocument()

    await user.click(within(editor).getByRole('button', { name: 'Guardar' }))
    expect(
      savedRiff(calls)?.events?.map((e) => [e.t, e.string, e.fret]),
    ).toEqual([
      [0, 5, 3],
      [2, 3, 7],
      [4, 2, 12],
    ])
  })

  it('un riff que se pasa de la sección muestra el error antes de guardar', async () => {
    const calls = mockApi(response('auto', content()))
    const { user, editor } = await openRiffEditor()
    const add = within(editor).getByRole('group', { name: 'Agregar nota' })
    const time = within(add).getByLabelText(/Tiempo/)
    await user.clear(time)
    await user.type(time, '7.5')
    await user.click(within(add).getByRole('button', { name: 'Agregar nota' }))

    expect(within(editor).getByRole('alert').textContent).toMatch(/se pasa/)
    const save = within(editor).getByRole('button', { name: 'Guardar' })
    expect(save).toBeDisabled()
    await user.click(save)
    expect(calls.some((c) => c.method === 'PUT')).toBe(false)
  })

  it('muestra legible un 422 de la API', async () => {
    mockApi(response('auto', content()), {
      putError: {
        status: 422,
        body: { detail: [{ msg: 'riff más largo que la sección' }] },
      },
    })
    const { user, editor } = await openRiffEditor()
    await user.click(within(editor).getByRole('button', { name: 'Guardar' }))
    const alert = await within(editor).findByRole('alert')
    expect(alert.textContent).toBe(
      'La API no aceptó el riff: riff más largo que la sección',
    )
    expect(
      within(editor).getByRole('button', { name: 'Guardar' }),
    ).toBeEnabled()
  })

  it('cancelar vuelve a la vista sin guardar', async () => {
    const calls = mockApi(response('auto', content()))
    const { user, editor } = await openRiffEditor()
    await user.click(within(editor).getByRole('button', { name: 'Cancelar' }))
    expect(screen.getByRole('button', { name: 'Editar tab' })).toBeTruthy()
    expect(calls.some((c) => c.method === 'PUT')).toBe(false)
  })

  it('"Agregar riff" crea uno desde cero en una sección sin riff', async () => {
    const calls = mockApi(response('auto', content(false)))
    const { user, editor } = await openRiffEditor('Agregar riff')
    // sin notas, guardar queda trabado por la validación
    expect(
      within(editor).getByRole('button', { name: 'Guardar' }),
    ).toBeDisabled()
    await user.click(
      within(editor).getByRole('button', { name: 'Agregar nota' }),
    )
    await user.click(within(editor).getByRole('button', { name: 'Guardar' }))
    expect(savedRiff(calls)).toEqual({
      bpm: 60,
      events: [{ t: 0, dur: 1, string: 1, fret: 0 }],
    })
  })

  it('"Volver a la automática" descarta la versión del usuario', async () => {
    const calls = mockApi(response('user', content()))
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/explorar/canciones/7']}>
        <Routes>
          <Route path="explorar/canciones/:id" element={<SongScreen />} />
        </Routes>
      </MemoryRouter>,
    )
    await user.click(await screen.findByRole('button', { name: 'Eléctrica' }))
    expect(await screen.findByText('Riff editado por vos')).toBeTruthy()
    const revert = screen.getAllByRole('button', {
      name: 'Volver a la automática',
    })
    await user.click(revert[revert.length - 1])
    await user.click(screen.getByRole('button', { name: 'Sí, volver' }))
    await vi.waitFor(() =>
      expect(calls.some((c) => c.method === 'DELETE')).toBe(true),
    )
    await vi.waitFor(() =>
      expect(
        screen.queryByText('Riff editado por vos'),
      ).not.toBeInTheDocument(),
    )
  })
})

describe('editor de tab a 375 px', () => {
  it('la grilla de controles encoge y la lista de notas envuelve', () => {
    expect(css).toMatch(/flex-wrap:\s*wrap/)
    expect(css).toMatch(/minmax\(min\(100%,/)
    expect(css).toMatch(/min-width:\s*0/)
    expect(css).not.toMatch(/(^|[^-])width:\s*\d{3,}px/)
  })

  it('solo usa tokens de color', () => {
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/)
    expect(css).not.toMatch(/rgba?\(|hsla?\(/)
  })
})
