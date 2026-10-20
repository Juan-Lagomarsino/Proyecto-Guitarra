import type { ClickSink, Clock, PlaybackAudio } from './clock'

const ACCENT_HZ = 1500
const NORMAL_HZ = 1000
const CLICK_SECONDS = 0.04
const CLICK_GAIN = 0.4
const FRAME_FALLBACK_MS = 25

/**
 * Reloj de producción: el tiempo es el `currentTime` del AudioContext.
 * Ojo: `currentTime` no compensa `outputLatency`; el resaltado puede
 * adelantarse unos ms al sonido.
 */
class AudioContextClock implements Clock {
  constructor(private readonly ctx: AudioContext) {}

  now(): number {
    return this.ctx.currentTime
  }

  every(fn: () => void, ms: number): () => void {
    const id = setInterval(fn, ms)
    return () => clearInterval(id)
  }

  onFrame(fn: () => void): () => void {
    if (typeof requestAnimationFrame !== 'function') {
      return this.every(fn, FRAME_FALLBACK_MS)
    }
    let id = 0
    let active = true
    const loop = () => {
      if (!active) return
      fn()
      if (active) id = requestAnimationFrame(loop)
    }
    id = requestAnimationFrame(loop)
    return () => {
      active = false
      cancelAnimationFrame(id)
    }
  }
}

class OscillatorClickSink implements ClickSink {
  private readonly pending = new Set<{ osc: OscillatorNode; start: number }>()

  constructor(private readonly ctx: AudioContext) {}

  click(time: number, accent: boolean): void {
    const osc = this.ctx.createOscillator()
    const gain = this.ctx.createGain()
    osc.frequency.value = accent ? ACCENT_HZ : NORMAL_HZ
    const start = Math.max(time, this.ctx.currentTime)
    gain.gain.setValueAtTime(CLICK_GAIN, start)
    gain.gain.exponentialRampToValueAtTime(0.001, start + CLICK_SECONDS)
    osc.connect(gain).connect(this.ctx.destination)
    const entry = { osc, start }
    this.pending.add(entry)
    osc.onended = () => {
      this.pending.delete(entry)
      osc.disconnect()
      gain.disconnect()
    }
    osc.start(start)
    osc.stop(start + CLICK_SECONDS)
  }

  cancel(): void {
    const now = this.ctx.currentTime
    for (const entry of this.pending) {
      if (entry.start <= now) continue
      this.pending.delete(entry)
      entry.osc.stop()
      entry.osc.disconnect()
    }
  }
}

/** Crea el audio real. Llamar desde un gesto del usuario (política de autoplay). */
export function createWebAudio(): PlaybackAudio {
  const ctx = new AudioContext()
  void ctx.resume()
  return {
    clock: new AudioContextClock(ctx),
    sink: new OscillatorClickSink(ctx),
    close: () => void ctx.close(),
  }
}
