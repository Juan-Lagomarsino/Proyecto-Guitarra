import type { TabAnnotation, TabColumn } from './columns'
import {
  LEFT_GUTTER,
  SYSTEM_HEIGHT,
  annotationX,
  layoutSystem,
  stringY,
} from './layout'

describe('annotationX', () => {
  const hammer = (fromT: number): TabAnnotation => ({
    text: 'h',
    placement: 'between',
    fromT,
  })
  const withAnnotation = (t: number, annotation: TabAnnotation): TabColumn => ({
    ...col(0, t),
    annotations: [annotation],
  })

  it('una anotación común queda centrada sobre la columna', () => {
    const l = layoutSystem([col(0, 0)])
    const on: TabAnnotation = { text: 'b1', placement: 'on' }
    expect(annotationX(l, l.columns[0], on)).toBe(l.columns[0].cx)
  })

  it('la ligadura queda a mitad de camino entre origen y destino', () => {
    const l = layoutSystem([col(0, 0), withAnnotation(1, hammer(0))])
    const [from, to] = l.columns
    expect(annotationX(l, to, hammer(0))).toBe((from.cx + to.cx) / 2)
  })

  it('si el origen está en el sistema anterior, va pegada al borde izquierdo', () => {
    const l = layoutSystem([withAnnotation(1, hammer(0))])
    const x = annotationX(l, l.columns[0], hammer(0))
    expect(x).toBeGreaterThan(LEFT_GUTTER)
    expect(x).toBeLessThan(l.columns[0].cx)
  })
})

const col = (bar: number, t: number, width = 30): TabColumn => ({
  t,
  dur: 1,
  bar,
  width,
  notes: [],
  annotations: [],
})

describe('stringY', () => {
  it('la cuerda 1 va arriba y la 6 abajo', () => {
    expect(stringY(1)).toBeLessThan(stringY(6))
    expect(stringY(6)).toBeLessThan(SYSTEM_HEIGHT)
  })
})

describe('layoutSystem', () => {
  it('apila las columnas a partir del margen izquierdo', () => {
    const l = layoutSystem([col(0, 0, 30), col(0, 1, 40)])
    expect(l.columns[0].x).toBe(LEFT_GUTTER)
    expect(l.columns[1].x).toBe(LEFT_GUTTER + 30)
    expect(l.columns[0].cx).toBeGreaterThan(l.columns[0].x)
  })

  it('pone barras de compás al cambiar de compás y al final', () => {
    const l = layoutSystem([col(0, 0), col(0, 1), col(1, 2)])
    expect(l.barLines).toEqual([LEFT_GUTTER + 60, l.endX])
  })

  it('termina en el borde derecho de la última columna', () => {
    const l = layoutSystem([col(0, 0, 30)])
    expect(l.endX).toBeGreaterThanOrEqual(LEFT_GUTTER + 30)
  })
})
