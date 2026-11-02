export interface LoopRange {
  startS: number
  endS: number
}

/**
 * Fuente de acompañamiento: la implementan el `<audio>` (F3-T02), las fuentes
 * sintetizadas (F3-T06) y, más adelante, el Rig. Todos los tiempos son
 * segundos de la canción.
 */
export interface BackingSource {
  play(): void
  pause(): void
  /** Salta a `seconds` (se acota a [0, duración]). */
  seek(seconds: number): void
  /** Posición actual; siempre se lee de la fuente, nunca se cuenta. */
  position(): number
  /** Velocidad sin cambio de tono; se acota a [0,5; 1,0]. */
  setRate(rate: number): void
  /** Loop A-B; `null` lo quita. Un rango inválido lanza error. */
  setLoop(loop: LoopRange | null): void
  isPlaying(): boolean
  /** Avisa cuando la fuente llega al final; devuelve la función que cancela. */
  onEnded(fn: () => void): () => void
  /** Libera recursos y deja de vigilar el loop. */
  dispose(): void
}
