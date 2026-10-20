const BASE_URL = '/api/v1'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

interface ApiRequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown }
    if (typeof data.detail === 'string') return data.detail
  } catch {
    // el cuerpo no era JSON: se usa el texto de estado
  }
  return response.statusText || `Error ${response.status}`
}

/** fetch tipado contra /api/v1 con el token Bearer de la config de build. */
export async function apiFetch<T = unknown>(
  path: string,
  { method = 'GET', body, signal }: ApiRequestOptions = {},
): Promise<T> {
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

  if (!response.ok)
    throw new ApiError(response.status, await readErrorMessage(response))
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
