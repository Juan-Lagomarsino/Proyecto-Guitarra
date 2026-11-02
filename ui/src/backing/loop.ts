import type { LoopRange } from './types'

/** Un loop vale si 0 <= A < B y, si se conoce la duración, B <= duración. */
export function isValidLoop(loop: LoopRange, durationS?: number): boolean {
  const { startS, endS } = loop
  if (!Number.isFinite(startS) || !Number.isFinite(endS)) return false
  if (startS < 0 || startS >= endS) return false
  if (durationS !== undefined && Number.isFinite(durationS) && endS > durationS)
    return false
  return true
}

/** Devuelve a dónde saltar si la posición pasó el final del loop; si no, `null`. */
export function loopJumpTarget(
  positionS: number,
  loop: LoopRange | null,
): number | null {
  if (loop === null) return null
  return positionS >= loop.endS ? loop.startS : null
}
