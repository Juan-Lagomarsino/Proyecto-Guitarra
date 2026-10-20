import type { TabAnnotation, TabColumn } from './columns'

/** Medidas tomadas de `drawTab` en docs/referencias/taller-electrica.html. */
export const LEFT_GUTTER = 22
export const STRING_GAP = 15
export const TOP_MARGIN = 22
export const SYSTEM_HEIGHT = TOP_MARGIN + 5 * STRING_GAP + 10
export const RIGHT_PADDING = 4
export const NOTE_BOX_HEIGHT = 15
export const ANNOTATION_Y = TOP_MARGIN - 10

/** Ancho que se descuenta del total para el nombre de cuerda y el borde derecho. */
export const SYSTEM_CHROME = LEFT_GUTTER + RIGHT_PADDING + 8

export interface PositionedColumn {
  column: TabColumn
  x: number
  /** Centro horizontal de las notas de la columna. */
  cx: number
}

export interface SystemLayout {
  columns: PositionedColumn[]
  barLines: number[]
  endX: number
}

/** Y de la cuerda 1..6: la 1 (aguda) arriba. */
export function stringY(string: number): number {
  return TOP_MARGIN + (string - 1) * STRING_GAP
}

/** Separación del símbolo de una ligadura que continúa respecto del borde del sistema. */
const CONTINUATION_INSET = 3

/**
 * X donde se dibuja una anotación de la columna `positioned`.
 * `between`: a mitad de camino entre la nota de origen y la de destino; si el
 * origen quedó en el sistema anterior, pegada al borde izquierdo (ligadura que continúa).
 */
export function annotationX(
  layout: SystemLayout,
  positioned: PositionedColumn,
  annotation: TabAnnotation,
): number {
  if (annotation.placement !== 'between') return positioned.cx
  const origin = layout.columns.find((c) => c.column.t === annotation.fromT)
  if (!origin) return LEFT_GUTTER + CONTINUATION_INSET
  return (origin.cx + positioned.cx) / 2
}

export function layoutSystem(columns: TabColumn[]): SystemLayout {
  const positioned: PositionedColumn[] = []
  const barLines: number[] = []
  let x = LEFT_GUTTER
  columns.forEach((column, i) => {
    if (i > 0 && columns[i - 1].bar !== column.bar) barLines.push(x)
    positioned.push({ column, x, cx: x + 13 })
    x += column.width
  })
  const endX = x + RIGHT_PADDING
  if (columns.length) barLines.push(endX)
  return { columns: positioned, barLines, endX }
}
