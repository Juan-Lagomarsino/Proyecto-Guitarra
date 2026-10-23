import { defaultTheme } from '../../theme/defaultTheme'

export const COLOR_FIELDS: ReadonlyArray<{ token: string; label: string }> = [
  { token: '--bg', label: 'Fondo' },
  { token: '--surface', label: 'Superficie' },
  { token: '--surface-2', label: 'Superficie 2' },
  { token: '--line', label: 'Líneas' },
  { token: '--text', label: 'Texto' },
  { token: '--muted', label: 'Texto atenuado' },
  { token: '--accent', label: 'Acento' },
  { token: '--accent-dim', label: 'Acento tenue' },
  { token: '--accent-ink', label: 'Tinta sobre acento' },
  { token: '--good', label: 'Acierto' },
  { token: '--good-dim', label: 'Acierto tenue' },
  { token: '--warn', label: 'Dato dudoso' },
  { token: '--wood', label: 'Madera del mástil' },
  { token: '--note-tonic', label: 'Nota tónica' },
  { token: '--note-other', label: 'Otras notas' },
  { token: '--note-active', label: 'Nota que suena' },
  { token: '--string', label: 'Cuerdas' },
  { token: '--fret', label: 'Trastes' },
]

export const FONT_FIELDS = [
  { token: '--font-display', label: 'Tipografía de títulos' },
  { token: '--font-mono', label: 'Tipografía de texto' },
] as const

export const FONT_PRESETS: Record<string, string[]> = {
  '--font-display': [
    defaultTheme['--font-display'],
    "Impact, 'Arial Narrow', sans-serif",
    "'Arial Narrow', Arial, sans-serif",
    'system-ui, sans-serif',
  ],
  '--font-mono': [
    defaultTheme['--font-mono'],
    'ui-monospace, Menlo, Consolas, monospace',
    "'Courier New', monospace",
  ],
}

const unquote = (value: string) => value.replace(/["']/g, '')

/** Compara tipografías sin importar el estilo de comillas. */
export const sameFont = (a: string, b: string) => unquote(a) === unquote(b)

export function fontLabel(stack: string): string {
  return unquote(stack.split(',')[0]).trim()
}

/** Las zonas que conoce el navegador, con la actual siempre incluida. */
export function timezoneOptions(current: string): string[] {
  const supported =
    typeof Intl.supportedValuesOf === 'function'
      ? Intl.supportedValuesOf('timeZone')
      : []
  return supported.includes(current) ? supported : [current, ...supported]
}
