const BASE_URL = '/api/v1'

export class ApiError extends Error {
  readonly status: number
  /** Campo `detail` de la respuesta de error (string, o lista en los 422 de FastAPI). */
  readonly detail: unknown

  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

interface ApiRequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
}

async function readError(
  response: Response,
): Promise<{ message: string; detail?: unknown }> {
  const fallback = response.statusText || `Error ${response.status}`
  try {
    const data = (await response.json()) as { detail?: unknown }
    const message = typeof data.detail === 'string' ? data.detail : fallback
    return { message, detail: data.detail }
  } catch {
    // el cuerpo no era JSON: se usa el texto de estado
    return { message: fallback }
  }
}

/** fetch tipado contra /api/v1 con el token Bearer de la config de build. */
export async function apiFetch<T = unknown>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  return (await apiFetchWithStatus<T>(path, options)).data
}

/** Igual que `apiFetch` pero devuelve también el status HTTP (200 vs 201). */
export async function apiFetchWithStatus<T = unknown>(
  path: string,
  { method = 'GET', body, signal }: ApiRequestOptions = {},
): Promise<{ status: number; data: T }> {
  const headers = new Headers({
    Authorization: `Bearer ${import.meta.env.VITE_GUITAR_API_TOKEN ?? ''}`,
  })
  if (body !== undefined) headers.set('Content-Type', 'application/json')

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  })

  if (!response.ok) {
    const { message, detail } = await readError(response)
    throw new ApiError(response.status, message, detail)
  }
  if (response.status === 204)
    return { status: response.status, data: undefined as T }
  return { status: response.status, data: (await response.json()) as T }
}
