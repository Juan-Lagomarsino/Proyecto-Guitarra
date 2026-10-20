import type { Clock, ClickSink, PlaybackAudio } from './clock'

const FRAME_MS = 25

interface Timer {
  fn: () => void
  everySeconds: number
  next: number
  active: boolean
}

/** Reloj falso para tests: el tiempo solo avanza con `advance`. */
export class FakeClock implements Clock {
  private time = 0
  private timers: Timer[] = []

  now(): number {
    return this.time
  }

  every(fn: () => void, ms: number): () => void {
    const timer: Timer = {
      fn,
      everySeconds: ms / 1000,
      next: this.time + ms / 1000,
      active: true,
    }
    this.timers.push(timer)
    return () => {
      timer.active = false
    }
  }

  onFrame(fn: () => void): () => void {
    return this.every(fn, FRAME_MS)
  }

  /** Cantidad de timers todavía activos (para verificar limpieza). */
  get activeTimers(): number {
    return this.timers.filter((t) => t.active).length
  }

  advance(seconds: number): void {
    const target = this.time + seconds
    for (;;) {
      this.timers = this.timers.filter((t) => t.active)
      const due = this.timers
        .filter((t) => t.next <= target + 1e-9)
        .sort((a, b) => a.next - b.next)[0]
      if (!due) break
      this.time = Math.max(this.time, due.next)
      due.next += due.everySeconds
      due.fn()
    }
    this.time = target
  }
}

export interface RecordedClick {
  time: number
  accent: boolean
}

/**
 * Registra los clics. `cancel()` descarta los que todavía no sonaron
 * (time > now del reloj) y los guarda en `cancelled`.
 */
export class RecordingSink implements ClickSink {
  clicks: RecordedClick[] = []
  cancelled: RecordedClick[] = []

  constructor(private readonly clock?: Clock) {}

  click(time: number, accent: boolean): void {
    this.clicks.push({ time, accent })
  }

  cancel(): void {
    const now = this.clock?.now() ?? Number.NEGATIVE_INFINITY
    this.cancelled.push(...this.clicks.filter((c) => c.time > now))
    this.clicks = this.clicks.filter((c) => c.time <= now)
  }
}

/** Audio de test: reloj falso + sink que registra, con `closed` para verificar el cierre. */
export class FakeAudio implements PlaybackAudio {
  readonly clock = new FakeClock()
  readonly sink = new RecordingSink(this.clock)
  closed = 0

  close(): void {
    this.closed++
  }
}
