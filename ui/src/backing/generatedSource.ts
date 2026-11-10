import type { Clock } from '../playback/clock'
import { isDownbeat } from '../playback/timing'
import type { SongChartContent } from '../songs/types'
import { generateArrangement, gridBeatsPerBar } from './arrangement'
import { clamp } from './clamp'
import { isValidLoop } from './loop'
import { MAX_RATE, MIN_RATE } from './mediaSource'
import type { SynthVoice, VoiceSink } from './synth'
import { beatsToSeconds, secondsToBeats } from './timeline'
import type { BackingSource, LoopRange } from './types'

export type GeneratedMode = 'click' | 'drums' | 'full'

const TICK_MS = 25
const LOOKAHEAD_SECONDS = 0.1
/** Margen para no repetir un evento que ya quedó agendado en la posición actual. */
const AFTER_EPSILON = 1e-9

/** Evento ya pasado a segundos de canción. */
interface TimedEvent {
  timeS: number
  durS: number
  voice: SynthVoice
  midi?: number | number[]
  velocity: number
}

export interface GeneratedSourceOptions {
  content: SongChartContent
  mode: GeneratedMode
  clock: Clock
  sink: VoiceSink
}

// ------------------------------------------------------------ tiempo

interface BeatMap {
  toSeconds(beat: number): number
  toBeats(seconds: number): number
}

function beatMap(content: SongChartContent): BeatMap {
  const grid = content.beat_grid?.beats_s
  if (grid && grid.length >= 2) {
    return {
      toSeconds: (beat) => beatsToSeconds(beat, grid),
      toBeats: (seconds) => secondsToBeats(seconds, grid),
    }
  }
  // Sin grilla, `bpm` es por beat de grilla (igual que en el arreglo).
  const secondsPerBeat = 60 / content.bpm
  return {
    toSeconds: (beat) => beat * secondsPerBeat,
    toBeats: (seconds) => seconds / secondsPerBeat,
  }
}

function songDuration(content: SongChartContent): number {
  const sectionsEnd = Math.max(...content.sections.map((s) => s.end_s))
  const grid = content.beat_grid?.beats_s
  const gridEnd = grid ? grid[grid.length - 1] : 0
  return Math.max(sectionsEnd, gridEnd)
}

// ------------------------------------------------------------ eventos

function clickEvents(
  content: SongChartContent,
  map: BeatMap,
  durationS: number,
): TimedEvent[] {
  const barLength = gridBeatsPerBar(content.time_signature)
  const downbeats = content.beat_grid?.downbeats_s ?? []
  const downbeatBeats = new Set(
    downbeats.map((t) => Math.round(map.toBeats(t))),
  )
  const accentAt = (beat: number) =>
    downbeatBeats.size > 0
      ? downbeatBeats.has(beat)
      : isDownbeat(beat, barLength)

  const events: TimedEvent[] = []
  for (let beat = 0; ; beat++) {
    const timeS = map.toSeconds(beat)
    if (timeS >= durationS) break
    events.push({
      timeS,
      durS: 0.04,
      voice: accentAt(beat) ? 'accent' : 'click',
      velocity: 1,
    })
  }
  return events
}

function arrangementEvents(
  content: SongChartContent,
  map: BeatMap,
  mode: 'drums' | 'full',
): TimedEvent[] {
  return generateArrangement(content)
    .filter(
      (e) => mode === 'full' || (e.voice !== 'bass' && e.voice !== 'chord'),
    )
    .map((e) => {
      const timeS = map.toSeconds(e.beat)
      return {
        timeS,
        durS: map.toSeconds(e.beat + e.durBeats) - timeS,
        voice: e.voice,
        midi: e.midi,
        velocity: e.velocity,
      }
    })
    .sort((a, b) => a.timeS - b.timeS)
}

function buildEvents(
  content: SongChartContent,
  mode: GeneratedMode,
  durationS: number,
): TimedEvent[] {
  const map = beatMap(content)
  return mode === 'click'
    ? clickEvents(content, map, durationS)
    : arrangementEvents(content, map, mode)
}

/** Índice del primer evento con `timeS >= value`. */
function lowerBound(events: readonly TimedEvent[], value: number): number {
  let low = 0
  let high = events.length
  while (low < high) {
    const mid = (low + high) >> 1
    if (events[mid].timeS < value) low = mid + 1
    else high = mid
  }
  return low
}

// ------------------------------------------------------------ fuente

/**
 * Acompañamiento sintetizado (metrónomo, batería o batería + bajo + acordes).
 * El tiempo es el del reloj inyectable: la posición se deriva de un ancla
 * (instante del reloj ↔ segundo de canción) y la velocidad, y el
 * planificador agenda con anticipación (ADR 0004). Cualquier cambio de
 * transporte cancela lo agendado y vuelve a planificar desde la posición.
 */
export class GeneratedBackingSource implements BackingSource {
  private readonly events: TimedEvent[]
  private readonly durationS: number
  private readonly clock: Clock
  private readonly sink: VoiceSink
  private readonly endedListeners = new Set<() => void>()

  private playing = false
  private rate = MAX_RATE
  private loop: LoopRange | null = null
  /** Segundo de canción en el instante `anchorTime` del reloj (o fijo si está en pausa). */
  private anchorSong = 0
  private anchorTime = 0
  /** Cursor del planificador: próximo segundo de canción por agendar y su instante. */
  private cursorSong = 0
  private cursorTime = 0
  private cursorExhausted = false
  private stopTimer: (() => void) | null = null

  constructor({ content, mode, clock, sink }: GeneratedSourceOptions) {
    this.clock = clock
    this.sink = sink
    this.durationS = songDuration(content)
    this.events = buildEvents(content, mode, this.durationS)
  }

  play(): Promise<void> {
    if (this.playing) return Promise.resolve()
    if (this.anchorSong >= this.durationS) this.anchorSong = 0
    this.playing = true
    this.reanchor(this.anchorSong, true)
    this.stopTimer = this.clock.every(() => this.tick(), TICK_MS)
    return Promise.resolve()
  }

  pause(): void {
    if (!this.playing) return
    const here = this.position()
    this.stopScheduling()
    this.playing = false
    this.anchorSong = here
  }

  seek(seconds: number): void {
    if (!Number.isFinite(seconds)) return
    this.moveTo(clamp(seconds, 0, this.durationS), true)
  }

  position(): number {
    if (!this.playing) return this.anchorSong
    const raw =
      this.anchorSong + (this.clock.now() - this.anchorTime) * this.rate
    return this.wrap(raw)
  }

  setRate(rate: number): void {
    if (!Number.isFinite(rate)) return
    const here = this.position()
    this.rate = clamp(rate, MIN_RATE, MAX_RATE)
    this.moveTo(here, false)
  }

  setLoop(loop: LoopRange | null): void {
    if (loop !== null && !isValidLoop(loop, this.durationS)) {
      throw new RangeError('Loop inválido: se requiere 0 ≤ A < B ≤ duración')
    }
    const here = this.position()
    this.loop = loop && { ...loop }
    // Si quedó fuera del loop, se vuelve a A como hace el `<audio>`.
    const outside = this.loop !== null && here >= this.loop.endS
    this.moveTo(outside ? this.loop!.startS : here, outside)
  }

  isPlaying(): boolean {
    return this.playing
  }

  onEnded(fn: () => void): () => void {
    this.endedListeners.add(fn)
    return () => this.endedListeners.delete(fn)
  }

  dispose(): void {
    this.stopScheduling()
    this.playing = false
    this.endedListeners.clear()
    this.loop = null
  }

  // ------------------------------------------------------------ interno

  /** Mueve la posición a `songS` y re-planifica. `inclusive`: suena un evento justo ahí. */
  private moveTo(songS: number, inclusive: boolean): void {
    if (!this.playing) {
      this.anchorSong = songS
      return
    }
    this.sink.cancel()
    this.reanchor(songS, inclusive)
  }

  private reanchor(songS: number, inclusive: boolean): void {
    this.anchorSong = songS
    this.anchorTime = this.clock.now()
    this.cursorSong = inclusive ? songS : songS + AFTER_EPSILON
    this.cursorTime = this.anchorTime
    this.cursorExhausted = false
    this.schedule()
  }

  private stopScheduling(): void {
    this.stopTimer?.()
    this.stopTimer = null
    this.sink.cancel()
  }

  /** Con loop, la posición cruda se pliega dentro de [A, B). */
  private wrap(raw: number): number {
    if (this.loop === null || raw < this.loop.endS) {
      return Math.min(raw, this.durationS)
    }
    const { startS, endS } = this.loop
    return startS + ((raw - startS) % (endS - startS))
  }

  private tick(): void {
    this.schedule()
    if (this.loop === null && this.rawPosition() >= this.durationS)
      this.finish()
  }

  private rawPosition(): number {
    return this.anchorSong + (this.clock.now() - this.anchorTime) * this.rate
  }

  private finish(): void {
    this.stopScheduling()
    this.playing = false
    this.anchorSong = this.durationS
    ;[...this.endedListeners].forEach((fn) => fn())
  }

  /** Agenda los eventos que caen antes del horizonte, plegando el loop. */
  private schedule(): void {
    const horizon = this.clock.now() + LOOKAHEAD_SECONDS
    while (!this.cursorExhausted && this.cursorTime < horizon) {
      const segmentEnd = this.loop?.endS ?? this.durationS
      const sliceEnd = Math.min(
        segmentEnd,
        this.cursorSong + (horizon - this.cursorTime) * this.rate,
      )
      this.emit(this.cursorSong, sliceEnd)
      this.cursorTime += (sliceEnd - this.cursorSong) / this.rate
      this.cursorSong = sliceEnd
      if (sliceEnd < segmentEnd) break
      if (this.loop === null) this.cursorExhausted = true
      else this.cursorSong = this.loop.startS
    }
  }

  /** Dispara los eventos con `fromS <= tiempo < toS`. */
  private emit(fromS: number, toS: number): void {
    for (let i = lowerBound(this.events, fromS); i < this.events.length; i++) {
      const event = this.events[i]
      if (event.timeS >= toS) break
      const time = this.cursorTime + (event.timeS - fromS) / this.rate
      this.sink.trigger(
        event.voice,
        time,
        event.durS / this.rate,
        event.midi,
        event.velocity,
      )
    }
  }
}
