import type { Clock } from '../playback/clock'
import { clamp } from './clamp'
import { isValidLoop, loopJumpTarget } from './loop'
import type { BackingSource, LoopRange } from './types'

export const MIN_RATE = 0.5
export const MAX_RATE = 1

/** Lo mínimo que se usa de un `HTMLMediaElement` (un media falso lo cumple en tests). */
export interface MediaLike {
  currentTime: number
  readonly duration: number
  readonly paused: boolean
  playbackRate: number
  preservesPitch: boolean
  mozPreservesPitch?: boolean
  webkitPreservesPitch?: boolean
  play(): Promise<void> | void
  pause(): void
  addEventListener(type: 'ended', fn: () => void): void
  removeEventListener(type: 'ended', fn: () => void): void
}

/** Acompañamiento sobre un `<audio>`: velocidad nativa sin cambio de tono y loop A-B. */
export class MediaBackingSource implements BackingSource {
  private loop: LoopRange | null = null
  private readonly stopFrames: () => void
  private readonly endedListeners = new Set<() => void>()
  private readonly handleEnded = () => {
    // Con loop activo, llegar al final del archivo no termina: vuelve a A.
    if (this.loop !== null) {
      this.media.currentTime = this.loop.startS
      this.play().catch(() => undefined)
      return
    }
    this.endedListeners.forEach((fn) => fn())
  }

  constructor(
    private readonly media: MediaLike,
    clock: Clock,
  ) {
    this.applyPitchPreservation()
    this.media.addEventListener('ended', this.handleEnded)
    this.stopFrames = clock.onFrame(() => this.checkLoop())
  }

  play(): Promise<void> {
    // El rechazo (p. ej. autoplay bloqueado) se propaga: lo muestra la UI.
    return Promise.resolve(this.media.play())
  }

  pause(): void {
    this.media.pause()
  }

  seek(seconds: number): void {
    if (!Number.isFinite(seconds)) return
    const duration = Number.isFinite(this.media.duration)
      ? this.media.duration
      : seconds
    this.media.currentTime = clamp(seconds, 0, Math.max(0, duration))
  }

  position(): number {
    return this.media.currentTime
  }

  setRate(rate: number): void {
    this.media.playbackRate = clamp(rate, MIN_RATE, MAX_RATE)
    this.applyPitchPreservation()
  }

  setLoop(loop: LoopRange | null): void {
    if (loop !== null && !isValidLoop(loop, this.media.duration)) {
      throw new RangeError('Loop inválido: se requiere 0 ≤ A < B ≤ duración')
    }
    this.loop = loop && { ...loop }
  }

  isPlaying(): boolean {
    return !this.media.paused
  }

  onEnded(fn: () => void): () => void {
    this.endedListeners.add(fn)
    return () => this.endedListeners.delete(fn)
  }

  dispose(): void {
    this.stopFrames()
    this.media.removeEventListener('ended', this.handleEnded)
    this.endedListeners.clear()
    this.loop = null
    this.media.pause()
  }

  private checkLoop(): void {
    const target = loopJumpTarget(this.media.currentTime, this.loop)
    if (target !== null) this.media.currentTime = target
  }

  private applyPitchPreservation(): void {
    this.media.preservesPitch = true
    if ('mozPreservesPitch' in this.media) this.media.mozPreservesPitch = true
    if ('webkitPreservesPitch' in this.media)
      this.media.webkitPreservesPitch = true
  }
}
