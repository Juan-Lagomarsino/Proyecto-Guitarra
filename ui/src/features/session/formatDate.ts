/** "2026-10-23" -> "viernes, 23 de octubre" (sin pasar por UTC). */
export function formatSessionDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString('es-AR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })
}
