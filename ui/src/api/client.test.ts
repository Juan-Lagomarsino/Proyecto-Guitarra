import { ApiError, apiFetch } from './client'

const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  vi.stubEnv('VITE_GUITAR_API_TOKEN', 'secreto')
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

describe('apiFetch', () => {
  it('pega a /api/v1 con el token Bearer y devuelve el JSON tipado', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ nombre: 'Juan' }))

    const data = await apiFetch<{ nombre: string }>('/settings')

    expect(data.nombre).toBe('Juan')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/settings')
    expect(new Headers(init.headers).get('Authorization')).toBe(
      'Bearer secreto',
    )
  })

  it('envía el cuerpo como JSON', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }))

    await apiFetch('/settings', {
      method: 'PUT',
      body: { timezone: 'America/Montevideo' },
    })

    const [, init] = fetchMock.mock.calls[0]
    expect(init.method).toBe('PUT')
    expect(init.body).toBe(JSON.stringify({ timezone: 'America/Montevideo' }))
    expect(new Headers(init.headers).get('Content-Type')).toBe(
      'application/json',
    )
  })

  it('devuelve undefined con 204', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }))

    await expect(
      apiFetch('/algo', { method: 'DELETE' }),
    ).resolves.toBeUndefined()
  })

  it('lanza ApiError con status y detalle cuando la respuesta no es ok', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'No autorizado' }, 401))

    const error = await apiFetch('/settings').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(401)
    expect((error as ApiError).message).toBe('No autorizado')
  })

  it('lanza ApiError aunque el cuerpo del error no sea JSON', async () => {
    fetchMock.mockResolvedValue(new Response('boom', { status: 500 }))

    const error = await apiFetch('/x').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(500)
  })
})
