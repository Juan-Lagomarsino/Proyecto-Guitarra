import { ApiError } from '../../api/client'

const STEP_LABELS: Record<string, string> = {
  source: 'Buscando la canción',
  download: 'Descargando el audio',
  tempo: 'Detectando el tempo',
  chords: 'Reconociendo acordes',
  structure: 'Detectando secciones',
  cifraclub: 'Consultando Cifra Club',
  strum: 'Proponiendo rasgueo',
  assemble: 'Armando la canción',
}

/** Paso del análisis en español; lo desconocido se muestra tal cual. */
export const stepLabel = (step: string) => STEP_LABELS[step] ?? step

const LINK_PATTERN =
  /^(https?:\/\/(www\.|m\.|music\.)?(youtube\.com|youtu\.be|open\.spotify\.com)\/\S+|spotify:track:\S+)$/i

/** Validación liviana: la que vale es la de la API. */
export const looksLikeSongLink = (value: string) =>
  LINK_PATTERN.test(value.trim())

function detailMessages(detail: unknown): string[] {
  if (typeof detail === 'string') return [detail]
  if (!Array.isArray(detail)) return []
  return detail.flatMap((item: unknown) => {
    const msg = (item as { msg?: unknown } | null)?.msg
    return typeof msg === 'string' ? [msg] : []
  })
}

/** Texto legible para un error de la API (incluye los 422 de FastAPI). */
export function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    const messages = detailMessages(error.detail)
    if (messages.length > 0) return messages.join('. ')
  }
  return error instanceof Error ? error.message : 'Error desconocido'
}
