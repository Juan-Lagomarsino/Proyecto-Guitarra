/**
 * Reloj inyectable. `now()` es la única fuente de verdad del tiempo (segundos).
 * `every` y `onFrame` solo despiertan al planificador o a la UI: nunca se
 * acumula tiempo contando despertares.
 */
export interface Clock {
  now(): number
  /** Llama a `fn` cada `ms` aproximadamente; devuelve la función que lo cancela. */
  every(fn: () => void, ms: number): () => void
  /** Llama a `fn` en cada cuadro de la UI (rAF si existe, intervalo si no). */
  onFrame(fn: () => void): () => void
}

/** Salida de sonido del metrónomo: un clic en el instante `time` del reloj. */
export interface ClickSink {
  click(time: number, accent: boolean): void
  /** Cancela los clics ya programados que todavía no sonaron. */
  cancel(): void
}

export interface PlaybackAudio {
  clock: Clock
  sink: ClickSink
  /** Libera los recursos de audio (cierra el AudioContext). */
  close(): void
}
