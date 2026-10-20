import type { TabColumn } from './columns'

const sumWidths = (columns: TabColumn[]) =>
  columns.reduce((sum, c) => sum + c.width, 0)

function splitIntoBars(columns: TabColumn[]): TabColumn[][] {
  const bars: TabColumn[][] = []
  for (const column of columns) {
    const last = bars[bars.length - 1]
    if (last && last[0].bar === column.bar) last.push(column)
    else bars.push([column])
  }
  return bars
}

/**
 * Reparte las columnas en sistemas (líneas de tablatura) que entren en `available`.
 * Prioriza compases enteros; un compás más ancho que el sistema se parte por columna.
 * Cada sistema tiene al menos una columna.
 */
export function partitionSystems(
  columns: TabColumn[],
  available: number,
): TabColumn[][] {
  const systems: TabColumn[][] = []
  let current: TabColumn[] = []
  let currentWidth = 0

  const closeCurrent = () => {
    if (current.length) systems.push(current)
    current = []
    currentWidth = 0
  }
  const append = (items: TabColumn[]) => {
    current.push(...items)
    currentWidth += sumWidths(items)
  }

  for (const bar of splitIntoBars(columns)) {
    const barWidth = sumWidths(bar)
    if (currentWidth + barWidth <= available) {
      append(bar)
      continue
    }
    closeCurrent()
    if (barWidth <= available) {
      append(bar)
      continue
    }
    for (const column of bar) {
      if (current.length && currentWidth + column.width > available)
        closeCurrent()
      append([column])
    }
  }
  closeCurrent()
  return systems
}
