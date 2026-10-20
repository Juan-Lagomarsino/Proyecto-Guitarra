import type { Notation } from '../notation/types'
import type { PlaybackAudio } from './clock'
import { Metronome } from './metronome'
import {
  endBeat,
  findActiveGroup,
  groupEvents,
  parseBarLength,
  secondsToBeats,
  type EventGroup,
} from './timing'

export type PlaybackMode = 'auto' | 'step'

export interface PlaybackSnapshot {
  /** Primer evento del grupo activo; null si no hay ninguno. */
  activeIndex: number | null
  /** Todos los eventos simultáneos del grupo activo. */
  activeIndices: number[]
  isPlaying: boolean
  mode: PlaybackMode
  bpm: number
}

export interface EngineOptions {
  /** Fábrica del audio; se llama recién en el primer `play` (gesto del usuario). */
  audio: () => PlaybackAudio
  bpm?: number
  metronome?: boolean
  countIn?: boolean
}

const BEAT_EPSILON = 1e-9
const MIN_BPM = 20
const MAX_BPM = 400
const NO_INDICES: number[] = []

/** Punto de referencia del transporte: en `time` (reloj) estábamos en `beat`, a `bpm`. */
interface Anchor {
  time: number
  beat: number
  bpm: number
}

/**
 * Motor de reproducción sin dependencias de React. El tiempo sale siempre
 * del reloj inyectado: la posición es `anchor.beat + (now - anchor.time)`
 * en beats, así cambiar el BPM solo reancla y conserva la posición.
 * Al terminar el ejercicio se detiene y vuelve al inicio con `activeIndex = null`.
 */
export class PlaybackEngine {
  private readonly groups: EventGroup[]
  private readonly end: number
  private readonly barLength: number
  private readonly listeners = new Set<() => void>()

  private bpm: number
  private mode: PlaybackMode = 'auto'
  private metronomeOn: boolean
  private countIn: boolean
  private playing = false
  private pausedBeat = 0
  private groupIndex = -1
  private anchor: Anchor | null = null
  private readonly audioFactory: () => PlaybackAudio
  private audio: PlaybackAudio | null = null
  private metronome: Metronome | null = null
  private stopPolling: (() => void) | null = null
  private snapshot: PlaybackSnapshot

  constructor(notation: Notation, options: EngineOptions) {
    this.groups = groupEvents(notation.events ?? [])
    this.end = endBeat(this.groups)
    this.barLength = parseBarLength(notation.time_signature)
    this.audioFactory = options.audio
    this.bpm = this.validBpm(options.bpm) ?? notation.bpm
    this.metronomeOn = options.metronome ?? false
    this.countIn = options.countIn ?? false
    this.snapshot = this.buildSnapshot()
  }

  // --- suscripción (useSyncExternalStore) ---

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  getSnapshot = (): PlaybackSnapshot => this.snapshot

  // --- control ---

  play(): void {
    if (this.playing || this.mode === 'step' || this.groups.length === 0) return
    this.audio ??= this.audioFactory()
    const startBeat =
      this.pausedBeat === 0 && this.countIn
        ? -Math.ceil(this.barLength)
        : this.pausedBeat
    this.anchor = {
      time: this.audio.clock.now(),
      beat: startBeat,
      bpm: this.bpm,
    }
    this.playing = true
    this.startMetronome(startBeat)
    this.stopPolling = this.audio.clock.onFrame(() => this.update())
    this.update()
  }

  pause(): void {
    if (!this.playing) return
    this.pausedBeat = this.currentBeat()
    this.halt()
    this.emit()
  }

  stop(): void {
    this.halt()
    this.pausedBeat = 0
    this.groupIndex = -1
    this.emit()
  }

  setBpm(value: number): void {
    const bpm = this.validBpm(value)
    if (bpm === null || bpm === this.bpm) return
    if (this.playing && this.audio) {
      const beat = this.currentBeat()
      this.anchor = { time: this.audio.clock.now(), beat, bpm }
      // Lo ya agendado está al tiempo viejo: se cancela y se reprograma desde el beat siguiente.
      this.startMetronome(Math.floor(beat + BEAT_EPSILON) + 1)
    }
    this.bpm = bpm
    this.emit()
  }

  setMode(mode: PlaybackMode): void {
    if (mode === this.mode) return
    this.pause()
    this.mode = mode
    if (mode === 'auto') this.pausedBeat = this.groups[this.groupIndex]?.t ?? 0
    this.emit()
  }

  next(): void {
    if (this.mode !== 'step' || this.groups.length === 0) return
    this.groupIndex = Math.min(this.groupIndex + 1, this.groups.length - 1)
    this.emit()
  }

  prev(): void {
    if (this.mode !== 'step' || this.groups.length === 0) return
    this.groupIndex = Math.max(this.groupIndex - 1, 0)
    this.emit()
  }

  setMetronome(on: boolean): void {
    this.metronomeOn = on
  }

  setCountIn(on: boolean): void {
    this.countIn = on
  }

  /**
   * Corta timers, clics y cierra el audio, sin notificar. Para desmontar.
   * Un `play` posterior recrea el audio (doble montaje de StrictMode).
   */
  dispose(): void {
    this.halt()
    this.audio?.close()
    this.audio = null
  }

  // --- internos ---

  private currentBeat(): number {
    if (!this.playing || !this.anchor || !this.audio) return this.pausedBeat
    const elapsed = this.audio.clock.now() - this.anchor.time
    return this.anchor.beat + secondsToBeats(elapsed, this.anchor.bpm)
  }

  private timeOfBeat = (beat: number): number => {
    const a = this.anchor as Anchor
    return a.time + ((beat - a.beat) * 60) / a.bpm
  }

  private startMetronome(firstBeat: number): void {
    const audio = this.audio as PlaybackAudio
    this.metronome?.stop()
    this.metronome = new Metronome(audio.clock, audio.sink, this.barLength)
    this.metronome.start(
      this.timeOfBeat,
      firstBeat,
      (beat) => beat < this.end && (beat < 0 || this.metronomeOn),
    )
  }

  private update(): void {
    const beat = this.currentBeat()
    if (beat >= this.end) {
      this.stop()
      return
    }
    const index = findActiveGroup(this.groups, beat)
    if (index !== this.groupIndex) {
      this.groupIndex = index
      this.emit()
    }
  }

  private halt(): void {
    this.stopPolling?.()
    this.stopPolling = null
    this.metronome?.stop()
    this.metronome = null
    this.playing = false
    this.anchor = null
  }

  private validBpm(value: number | undefined): number | null {
    if (value === undefined || !Number.isFinite(value) || value <= 0)
      return null
    return Math.min(MAX_BPM, Math.max(MIN_BPM, value))
  }

  private buildSnapshot(): PlaybackSnapshot {
    const indices = this.groups[this.groupIndex]?.indices ?? NO_INDICES
    return {
      activeIndex: indices.length > 0 ? indices[0] : null,
      activeIndices: indices,
      isPlaying: this.playing,
      mode: this.mode,
      bpm: this.bpm,
    }
  }

  private emit(): void {
    this.snapshot = this.buildSnapshot()
    this.listeners.forEach((listener) => listener())
  }
}
