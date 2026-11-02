/** Posición en beats (el primer beat es 0): interpola entre beats y extrapola con el borde. */
export function secondsToBeats(tS: number, beatsS: readonly number[]): number {
  if (beatsS.length < 2) throw new Error('beats_s necesita al menos 2 beats')
  const index = Math.min(
    Math.max(upperBound(beatsS, tS) - 1, 0),
    beatsS.length - 2,
  )
  const start = beatsS[index]
  const end = beatsS[index + 1]
  return index + (tS - start) / (end - start)
}

/** Inversa de `secondsToBeats`: segundo en que cae `beat`, con la misma extrapolación. */
export function beatsToSeconds(
  beat: number,
  beatsS: readonly number[],
): number {
  if (beatsS.length < 2) throw new Error('beats_s necesita al menos 2 beats')
  const index = Math.min(Math.max(Math.floor(beat), 0), beatsS.length - 2)
  return beatsS[index] + (beat - index) * (beatsS[index + 1] - beatsS[index])
}

/** Cantidad de elementos <= value (equivale a bisect_right). */
function upperBound(sorted: readonly number[], value: number): number {
  let low = 0
  let high = sorted.length
  while (low < high) {
    const mid = (low + high) >> 1
    if (sorted[mid] <= value) low = mid + 1
    else high = mid
  }
  return low
}
