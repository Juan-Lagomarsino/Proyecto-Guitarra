import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import App from '../../App'
import { defaultTheme } from '../../theme/defaultTheme'
import { SettingsScreen } from './SettingsScreen'
import { SavedThemeProvider } from './SavedTheme'
import type { AppSettings } from './settingsApi'

const {
  '--font-display': DISPLAY,
  '--font-mono': MONO,
  ...COLORS
} = defaultTheme

const stored = (over: Partial<AppSettings> = {}): AppSettings => ({
  timezone: 'America/Montevideo',
  theme_tokens: { ...COLORS, '--accent': '#112233' },
  fonts: { '--font-display': DISPLAY, '--font-mono': MONO },
  default_instrument: 'electric',
  tuning: ['E2', 'A2', 'D3', 'G3', 'B3', 'E4'],
  ...over,
})

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

let fetchMock: ReturnType<typeof vi.fn>

const mockApi = (
  settings: AppSettings,
  put: (body: AppSettings) => Response = (body) => json(body),
) => {
  fetchMock = vi.fn(async (_url: string, init?: RequestInit) =>
    init?.method === 'PUT'
      ? put(JSON.parse(init.body as string) as AppSettings)
      : json(settings),
  )
  vi.stubGlobal('fetch', fetchMock)
}

const putCalls = () =>
  fetchMock.mock.calls.filter(([, init]) => init?.method === 'PUT')

const renderScreen = () =>
  render(
    <SavedThemeProvider>
      <SettingsScreen />
    </SavedThemeProvider>,
  )

const accentField = () => screen.findByLabelText(/^Acento\s*--accent$/)

beforeEach(() => {
  document.documentElement.removeAttribute('style')
})
afterEach(() => vi.unstubAllGlobals())

describe('SettingsScreen', () => {
  it('carga los ajustes y muestra un selector por cada token', async () => {
    mockApi(stored())
    renderScreen()

    expect(await accentField()).toHaveValue('#112233')
    expect(screen.getAllByLabelText(/--[a-z0-9-]+$/)).toHaveLength(
      Object.keys(COLORS).length,
    )
    expect(screen.getByLabelText('Tipografía de títulos')).toBeInTheDocument()
    expect(screen.getByLabelText('Tipografía de texto')).toBeInTheDocument()
    expect(screen.getByLabelText('Zona horaria')).toHaveValue(
      'America/Montevideo',
    )
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/settings')
  })

  it('avisa si no se pueden cargar', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({}, 500)))
    renderScreen()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /no se pudieron cargar/i,
    )
  })

  it('la vista previa se actualiza en vivo y no toca el tema de la app', async () => {
    mockApi(stored())
    renderScreen()
    const input = await accentField()
    const preview = screen.getByLabelText('Vista previa del tema')
    expect(preview.style.getPropertyValue('--accent')).toBe('#112233')

    await userEvent.clear(input)
    await userEvent.type(input, 'rebeccapurple')

    expect(preview.style.getPropertyValue('--accent')).toBe('rebeccapurple')
    expect(preview).toContainElement(
      screen.getByRole('img', { name: /mástil/i }),
    )
    expect(putCalls()).toHaveLength(0)
  })

  it('guardar envía el PUT con todos los tokens, los campos intactos y aplica el tema', async () => {
    mockApi(stored())
    renderScreen()
    const input = await accentField()
    await userEvent.clear(input)
    await userEvent.type(input, 'rebeccapurple')
    await userEvent.selectOptions(
      screen.getByLabelText('Zona horaria'),
      'Europe/Madrid',
    )
    await userEvent.selectOptions(
      screen.getByLabelText('Tipografía de texto'),
      "'Courier New', monospace",
    )
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(await screen.findByText('Ajustes guardados.')).toBeInTheDocument()
    expect(putCalls()).toHaveLength(1)
    const [url, init] = putCalls()[0]
    expect(url).toBe('/api/v1/settings')
    const body = JSON.parse(init.body as string) as AppSettings
    expect(body.timezone).toBe('Europe/Madrid')
    expect(body.theme_tokens).toEqual({
      ...COLORS,
      '--accent': 'rebeccapurple',
    })
    expect(body.fonts).toEqual({
      '--font-display': DISPLAY,
      '--font-mono': "'Courier New', monospace",
    })
    expect(body.default_instrument).toBe('electric')
    expect(body.tuning).toEqual(['E2', 'A2', 'D3', 'G3', 'B3', 'E4'])
    expect(document.documentElement.style.getPropertyValue('--accent')).toBe(
      'rebeccapurple',
    )
  })

  it('"Volver al tema por defecto" restaura colores y tipografías en el borrador', async () => {
    mockApi(
      stored({
        fonts: {
          '--font-display': 'system-ui, sans-serif',
          '--font-mono': MONO,
        },
      }),
    )
    renderScreen()
    const input = await accentField()
    expect(input).toHaveValue('#112233')

    await userEvent.click(
      screen.getByRole('button', { name: 'Volver al tema por defecto' }),
    )

    expect(input).toHaveValue(defaultTheme['--accent'])
    expect(screen.getByLabelText('Tipografía de títulos')).toHaveValue(DISPLAY)
    expect(putCalls()).toHaveLength(0)

    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await screen.findByText('Ajustes guardados.')
    const body = JSON.parse(putCalls()[0][1].body as string) as AppSettings
    expect(body.theme_tokens).toEqual(COLORS)
    expect(body.fonts['--font-display']).toBe(DISPLAY)
  })

  it('muestra los errores 422 de forma entendible', async () => {
    mockApi(stored(), () =>
      json(
        {
          detail: [
            {
              type: 'value_error',
              loc: ['body'],
              msg: "Value error, --accent: color CSS inválido: 'azulito'",
            },
          ],
        },
        422,
      ),
    )
    renderScreen()
    await accentField()
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent("--accent: color CSS inválido: 'azulito'")
    expect(alert).not.toHaveTextContent('Value error')
    expect(
      document.documentElement.style.getPropertyValue('--accent'),
    ).not.toBe('azulito')
  })

  it('muestra un mensaje genérico si falla el guardado', async () => {
    mockApi(stored(), () => json({ detail: 'boom' }, 500))
    renderScreen()
    await accentField()
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /no se pudo guardar/i,
    )
  })
})

describe('tema guardado al iniciar', () => {
  it('App aplica el tema de GET /settings', async () => {
    mockApi(stored())
    render(
      <MemoryRouter initialEntries={['/ajustes']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() =>
      expect(document.documentElement.style.getPropertyValue('--accent')).toBe(
        '#112233',
      ),
    )
  })

  it('si la API falla, queda el tema por defecto', async () => {
    const failing = vi.fn().mockRejectedValue(new Error('sin red'))
    vi.stubGlobal('fetch', failing)
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => expect(failing).toHaveBeenCalled())
    expect(document.documentElement.style.getPropertyValue('--accent')).toBe(
      defaultTheme['--accent'],
    )
  })
})
