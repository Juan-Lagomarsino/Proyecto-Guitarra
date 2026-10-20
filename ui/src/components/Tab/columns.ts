import type { NoteEvent } from '../../notation/types'

export type Tuning = [string, string, string, string, string, string]

export interface TabNote {
  /** Posición del evento en `notation.events`. */
  index: number
  string: number
  /** Texto dibujado sobre la cuerda: el traste, o `x` si es nota muerta. */
  label: string
}

export interface TabAnnotation {
  text: string
  /** `on`: centrada sobre la columna; `between`: entre la nota de origen y esta (destino). */
  placement: 'on' | 'between'
  /** Solo con `between`: `t` de la columna de la nota de origen. */
  fromT?: number
}

export interface TabColumn {
  t: number
  dur: number
  /** Número de compás (desde 0) al que pertenece la columna. */
  bar: number
  width: number
  notes: TabNote[]
  annotations: TabAnnotation[]
}

const DEFAULT_BEATS_PER_BAR = 4
const MIN_COLUMN_WIDTH = 26
const MAX_COLUMN_WIDTH = 72
const WIDTH_PER_EXTRA_BEAT = 20
const TIME_PRECISION = 1e6

/** Negras por compás a partir de una firma como "4/4" o "6/8". */
export function beatsPerBar(timeSignature: string | undefined): number {
  const match = /^(\d+)\/(\d+)$/.exec(timeSignature ?? '')
  if (!match) return DEFAULT_BEATS_PER_BAR
  const [numerator, denominator] = [Number(match[1]), Number(match[2])]
  if (numerator <= 0 || denominator <= 0) return DEFAULT_BEATS_PER_BAR
  return (numerator * 4) / denominator
}

/**
 * Ancho de una columna. Parte de `drawTab` (columnas de ~26 px con tope de 72),
 * pero acá `dur` está en beats y no en las unidades de la referencia: se suman
 * 20 px por beat extra (la referencia usa 10 por unidad) y se fija un piso de 26
 * para que corcheas y semicorcheas no se amontonen. Son decisiones propias.
 */
export function columnWidth(dur: number): number {
  const width = MIN_COLUMN_WIDTH + WIDTH_PER_EXTRA_BEAT * (dur - 1)
  return Math.min(MAX_COLUMN_WIDTH, Math.max(MIN_COLUMN_WIDTH, width))
}

/** Nombre de la cuerda 1..6 (1 = aguda) según la afinación, que va de grave a aguda. */
export function stringName(tuning: Tuning, string: number): string {
  const note = tuning[6 - string].replace(/\d+$/, '')
  return string === 1 ? note.toLowerCase() : note
}

function formatBend(bend: number | null | undefined): string {
  if (bend == null) return ''
  const whole = Math.floor(bend)
  if (bend - whole === 0.5) return `${whole === 0 ? '' : whole}½`
  return String(bend)
}

const BETWEEN_NOTES = new Set(['h', 'p', '/', '\\'])

interface Group {
  t: number
  items: { event: NoteEvent; index: number }[]
}

/** Redondea `t` para que 0.1 + 0.2 y 0.3 caigan en la misma columna. */
const normalizeTime = (t: number) =>
  Math.round(t * TIME_PRECISION) / TIME_PRECISION

/**
 * Las técnicas de dos notas se anotan en la nota de destino (formato oficial).
 * El origen es el evento anterior en la misma cuerda; si no hay, la columna previa.
 * Devuelve el `t` de la columna origen, o null si no hay ninguna anterior.
 */
function originTime(
  groups: Group[],
  at: number,
  string: number,
): number | null {
  if (at === 0) return null
  for (let j = at - 1; j >= 0; j--) {
    if (groups[j].items.some(({ event }) => event.string === string))
      return groups[j].t
  }
  return groups[at - 1].t
}

function annotationFor(
  groups: Group[],
  at: number,
  event: NoteEvent,
): TabAnnotation | null {
  const technique = event.technique
  if (!technique || technique === 'x') return null
  if (technique === 'pm') return { text: 'PM', placement: 'on' }
  if (technique === 'b')
    return { text: `b${formatBend(event.bend)}`, placement: 'on' }
  if (!BETWEEN_NOTES.has(technique)) return { text: technique, placement: 'on' }
  const fromT = originTime(groups, at, event.string)
  if (fromT === null) return { text: technique, placement: 'on' }
  return { text: technique, placement: 'between', fromT }
}

function uniqueAnnotations(groups: Group[], at: number): TabAnnotation[] {
  const seen = new Map<string, TabAnnotation>()
  for (const { event } of groups[at].items) {
    const annotation = annotationFor(groups, at, event)
    if (annotation && !seen.has(annotation.text))
      seen.set(annotation.text, annotation)
  }
  return [...seen.values()]
}

function groupByTime(events: NoteEvent[]): Group[] {
  const byTime = new Map<number, Group>()
  events.forEach((event, index) => {
    const t = normalizeTime(event.t)
    const group = byTime.get(t) ?? { t, items: [] }
    group.items.push({ event, index })
    byTime.set(t, group)
  })
  return [...byTime.values()].sort((a, b) => a.t - b.t)
}

/** Agrupa los eventos por instante `t`: los simultáneos comparten columna. */
export function buildColumns(
  events: NoteEvent[],
  beatsInBar: number,
): TabColumn[] {
  const groups = groupByTime(events)
  return groups.map((group, at) => {
    const dur = Math.max(...group.items.map(({ event }) => event.dur))
    return {
      t: group.t,
      dur,
      bar: Math.floor(group.t / beatsInBar),
      width: columnWidth(dur),
      notes: group.items.map(({ event, index }) => ({
        index,
        string: event.string,
        label: event.technique === 'x' ? 'x' : String(event.fret),
      })),
      annotations: uniqueAnnotations(groups, at),
    }
  })
}
