const CATEGORY_LABELS: Record<string, string> = {
  warmup: 'Calentamiento',
  technique: 'Técnica',
  riff: 'Riff',
  improvisation: 'Improvisación',
}

/** Nombre en español de una categoría de ejercicio; con un slug desconocido devuelve el slug. */
export function categoryLabel(slug: string): string {
  return CATEGORY_LABELS[slug] ?? slug
}
