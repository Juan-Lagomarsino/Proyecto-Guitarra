/**
 * Tema por defecto ("taller de eléctrica"), tomado del :root de
 * docs/referencias/taller-electrica.html. Debe coincidir con tokens.css
 * (hay un test que lo verifica).
 *
 * Correspondencia con la referencia:
 *   --ground -> --bg            --panel -> --surface       --panel2 -> --surface-2
 *   --ink -> --text             --sodium -> --accent       --sodium-dim -> --accent-dim
 *   --sodium-ink -> --accent-ink
 *   --note -> --note-other      (puntos de nota en drawBoard)
 *   --sodium -> --note-tonic    (nota raíz en drawBoard)
 *   --ink -> --note-active      (nota que suena en drawBoard)
 *   --muted -> --string         (cuerdas en drawBoard)
 *   --line -> --fret            (trastes en drawBoard)
 */
export type ThemeTokens = Record<string, string>

export const defaultTheme = {
  '--bg': '#14121f',
  '--surface': '#1f1c30',
  '--surface-2': '#262240',
  '--line': '#34304d',
  '--text': '#f3efe4',
  '--muted': '#9a95b3',
  '--accent': '#ffb534',
  '--accent-dim': '#7a5a22',
  '--accent-ink': '#1b1405',
  '--good': '#6fd39a',
  '--good-dim': '#1f4a35',
  '--warn': '#ff7a6b',
  '--wood': '#1a1729',
  '--note-tonic': '#ffb534',
  '--note-other': '#3a3558',
  '--note-active': '#f3efe4',
  '--string': '#9a95b3',
  '--fret': '#34304d',
  '--font-display': '"Anton", Impact, "Arial Narrow", sans-serif',
  '--font-mono': '"IBM Plex Mono", ui-monospace, Menlo, monospace',
} as const satisfies ThemeTokens
