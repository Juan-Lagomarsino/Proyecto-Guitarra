import type { CalendarDay } from '../../api/progress'

export interface HeatCell {
  date: string
  count: number
  level: 0 | 1 | 2 | 3 | 4
}

export interface HeatWeek {
  /** 7 posiciones (lunes a domingo); null = fuera del rango pedido. */
  cells: (HeatCell | null)[]
  /** Nombre del mes si la semana abre un mes nuevo, si no ''. */
  monthLabel: string
}

const MONTHS = [
  'ene',
  'feb',
  'mar',
  'abr',
  'may',
  'jun',
  'jul',
  'ago',
  'sep',
  'oct',
  'nov',
  'dic',
]

export const WEEKDAY_LABELS = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']

export function toIsoDate(d: Date): string {
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

function addDays(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n)
}

function parseIso(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** Rango del heatmap: del mismo día un año atrás hasta hoy, inclusive. */
export function yearRange(today: Date): { from: string; to: string } {
  const start = new Date(
    today.getFullYear() - 1,
    today.getMonth(),
    today.getDate(),
  )
  return { from: toIsoDate(start), to: toIsoDate(today) }
}

export function heatLevel(count: number): HeatCell['level'] {
  if (count <= 0) return 0
  if (count === 1) return 1
  if (count === 2) return 2
  if (count <= 4) return 3
  return 4
}

function buildCell(day: Date, counts: Map<string, number>): HeatCell {
  const date = toIsoDate(day)
  const count = counts.get(date) ?? 0
  return { date, count, level: heatLevel(count) }
}

/** Columnas por semana (lunes primero) entre `from` y `to`. */
export function buildWeeks(
  from: string,
  to: string,
  days: CalendarDay[],
): HeatWeek[] {
  const counts = new Map(days.map((d) => [d.date, d.count]))
  const start = parseIso(from)
  const end = parseIso(to)
  const offset = (start.getDay() + 6) % 7
  const weeks: HeatWeek[] = []
  let lastMonth = -1
  for (
    let weekStart = addDays(start, -offset);
    weekStart <= end;
    weekStart = addDays(weekStart, 7)
  ) {
    const cells = Array.from({ length: 7 }, (_, i) => {
      const day = addDays(weekStart, i)
      return day < start || day > end ? null : buildCell(day, counts)
    })
    const first = cells.find((c) => c !== null)
    const month = first ? parseIso(first.date).getMonth() : lastMonth
    weeks.push({
      cells,
      monthLabel: month !== lastMonth ? MONTHS[month] : '',
    })
    lastMonth = month
  }
  return weeks
}

export function cellLabel(cell: HeatCell): string {
  const [y, m, d] = cell.date.split('-')
  const what =
    cell.count === 0
      ? 'sin ejercicios'
      : cell.count === 1
        ? '1 ejercicio'
        : `${cell.count} ejercicios`
  return `${d}/${m}/${y}: ${what}`
}
