import { isLowConfidenceEvent } from '../../notation/confidence'
import type { Notation } from '../../notation/types'
import './LowConfidenceLegend.css'

/** Leyenda de las notas poco seguras; no dibuja nada si la notación no tiene ninguna. */
export function LowConfidenceLegend({
  notation,
  below,
}: {
  notation: Notation
  below: number
}) {
  const hasLow = (notation.events ?? []).some((event) =>
    isLowConfidenceEvent(event, below),
  )
  if (!hasLow) return null
  return (
    <p className="low-confidence-legend">
      <i className="low-confidence-legend__swatch" />
      Poco seguro: revisá estas notas de oído.
    </p>
  )
}
