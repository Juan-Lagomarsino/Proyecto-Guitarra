import { ApiError, apiFetch } from '../../api/client'

/** Espejo de `AppSettings` (api/src/guitarra_api/domain/app_settings.py). */
export interface AppSettings {
  timezone: string
  theme_tokens: Record<string, string>
  fonts: Record<string, string>
  default_instrument: 'classical' | 'electric'
  tuning: string[]
}

export const getSettings = (signal?: AbortSignal) =>
  apiFetch<AppSettings>('/settings', { signal })

export const putSettings = (settings: AppSettings) =>
  apiFetch<AppSettings>('/settings', { method: 'PUT', body: settings })

/** Tema plano (colores + tipografías) tal como lo consume ThemeProvider. */
export const toTheme = ({
  theme_tokens,
  fonts,
}: Pick<AppSettings, 'theme_tokens' | 'fonts'>): Record<string, string> => ({
  ...theme_tokens,
  ...fonts,
})

const VALUE_ERROR_PREFIX = /^Value error,\s*/

/** Mensajes legibles de un error de la API: lista de 422 de FastAPI o texto suelto. */
export function describeSaveError(error: unknown): string[] {
  if (error instanceof ApiError && error.status === 422) {
    if (Array.isArray(error.detail)) {
      const messages = error.detail
        .map((item) => (item as { msg?: unknown } | null)?.msg)
        .filter((msg): msg is string => typeof msg === 'string')
        .map((msg) => msg.replace(VALUE_ERROR_PREFIX, ''))
      if (messages.length > 0) return messages
    }
    return ['Hay valores que el servidor no aceptó. Revisá los campos.']
  }
  return ['No se pudo guardar. Probá de nuevo en un momento.']
}
