import { playClickTone } from '../audio/clickTone'
import type { BackingVoice } from './arrangement'

export type SynthVoice = BackingVoice | 'click' | 'accent'

/**
 * Salida de las fuentes generadas: dispara una voz en el instante `time` del
 * reloj de audio. `durS` es la duración en segundos reales; `midi` solo lo
 * usan bajo y acordes. La implementa el sintetizador y los tests.
 */
export interface VoiceSink {
  trigger(
    voice: SynthVoice,
    time: number,
    durS: number,
    midi: number | number[] | undefined,
    velocity: number,
  ): void
  /** Cancela lo ya agendado que todavía no sonó. */
  cancel(): void
}

const MASTER_GAIN = 0.5
const SILENCE = 0.001
const NOISE_SECONDS = 1
/** Cierre de las voces en curso al cancelar (evita el clic seco de cortar de golpe). */
const FADE_SECONDS = 0.025

const midiToHz = (midi: number) => 440 * 2 ** ((midi - 69) / 12)

interface Scheduled {
  start: number
  sources: Source[]
  envelopes: GainNode[]
  fading: boolean
}

type Source = OscillatorNode | AudioBufferSourceNode

/**
 * Sintetizador Web Audio sin samples: osciladores y ruido. Cada disparo
 * arma su propio grafo, que se desconecta solo al terminar.
 */
export class WebAudioVoiceSink implements VoiceSink {
  private readonly master: GainNode
  private readonly noise: AudioBuffer
  private readonly pending = new Set<Scheduled>()

  constructor(private readonly ctx: AudioContext) {
    this.master = ctx.createGain()
    this.master.gain.value = MASTER_GAIN
    this.master.connect(ctx.destination)
    this.noise = this.createNoise()
  }

  trigger(
    voice: SynthVoice,
    time: number,
    durS: number,
    midi: number | number[] | undefined,
    velocity: number,
  ): void {
    const start = Math.max(time, this.ctx.currentTime)
    const notes = midi === undefined ? [] : [midi].flat()
    switch (voice) {
      case 'kick':
        return this.kick(start, velocity)
      case 'snare':
        return this.snare(start, velocity)
      case 'hihat':
        return this.hihat(start, velocity)
      case 'bass':
        return this.bass(start, durS, notes[0], velocity)
      case 'chord':
        return this.chord(start, durS, notes, velocity)
      case 'click':
      case 'accent':
        return this.click(start, voice === 'accent')
    }
  }

  cancel(): void {
    const now = this.ctx.currentTime
    for (const entry of this.pending) {
      if (entry.start > now) {
        this.pending.delete(entry)
        entry.sources.forEach((s) => s.stop())
      } else if (!entry.fading) {
        this.fadeOut(entry, now)
      }
    }
  }

  /** Voz ya empezada: baja la ganancia en ~25 ms y la detiene. */
  private fadeOut(entry: Scheduled, now: number): void {
    entry.fading = true
    for (const gain of entry.envelopes) {
      gain.gain.cancelScheduledValues(now)
      gain.gain.setTargetAtTime(0, now, FADE_SECONDS / 4)
    }
    entry.sources.forEach((s) => s.stop(now + FADE_SECONDS))
  }

  // ------------------------------------------------------------- voces

  private kick(start: number, velocity: number): void {
    const osc = this.ctx.createOscillator()
    osc.frequency.setValueAtTime(150, start)
    osc.frequency.exponentialRampToValueAtTime(45, start + 0.12)
    const out = this.envelope(start, 0.3, velocity, 0.003)
    this.play(start, start + 0.3, [osc], [out], [])
    osc.connect(out)
  }

  private snare(start: number, velocity: number): void {
    const noise = this.noiseSource()
    const filter = this.ctx.createBiquadFilter()
    filter.type = 'bandpass'
    filter.frequency.value = 2500
    const noiseOut = this.envelope(start, 0.18, velocity * 0.7, 0.002)
    noise.connect(filter).connect(noiseOut)

    const tone = this.ctx.createOscillator()
    tone.type = 'triangle'
    tone.frequency.value = 190
    const toneOut = this.envelope(start, 0.1, velocity * 0.5, 0.002)
    tone.connect(toneOut)

    this.play(start, start + 0.18, [noise, tone], [noiseOut, toneOut], [filter])
  }

  private hihat(start: number, velocity: number): void {
    const noise = this.noiseSource()
    const filter = this.ctx.createBiquadFilter()
    filter.type = 'highpass'
    filter.frequency.value = 7000
    const out = this.envelope(start, 0.05, velocity * 0.5, 0.001)
    noise.connect(filter).connect(out)
    this.play(start, start + 0.05, [noise], [out], [filter])
  }

  private bass(
    start: number,
    durS: number,
    midi: number | undefined,
    velocity: number,
  ): void {
    if (midi === undefined) return
    const length = Math.max(durS, 0.1)
    const osc = this.ctx.createOscillator()
    osc.type = 'sawtooth'
    osc.frequency.value = midiToHz(midi)
    const filter = this.ctx.createBiquadFilter()
    filter.type = 'lowpass'
    filter.frequency.value = 500
    const out = this.envelope(start, length, velocity * 0.8, 0.01)
    osc.connect(filter).connect(out)
    this.play(start, start + length, [osc], [out], [filter])
  }

  private chord(
    start: number,
    durS: number,
    notes: number[],
    velocity: number,
  ): void {
    if (notes.length === 0) return
    const length = Math.max(durS, 0.2)
    const filter = this.ctx.createBiquadFilter()
    filter.type = 'lowpass'
    filter.frequency.value = 1800
    const out = this.envelope(
      start,
      length,
      (velocity * 0.6) / notes.length ** 0.5,
      0.04,
    )
    filter.connect(out)
    const oscs = notes.map((midi) => {
      const osc = this.ctx.createOscillator()
      osc.type = 'triangle'
      osc.frequency.value = midiToHz(midi)
      osc.connect(filter)
      return osc
    })
    this.play(start, start + length, oscs, [out], [filter])
  }

  private click(start: number, accent: boolean): void {
    const { osc, gain } = playClickTone(this.ctx, this.master, start, accent)
    this.track(start, [osc], [gain], [])
  }

  // ------------------------------------------------------------ soporte

  /** Ganancia con ataque corto y caída exponencial hasta `start + length`; sale al master. */
  private envelope(
    start: number,
    length: number,
    peak: number,
    attack: number,
  ): GainNode {
    const gain = this.ctx.createGain()
    gain.gain.setValueAtTime(SILENCE, start)
    gain.gain.linearRampToValueAtTime(Math.max(peak, SILENCE), start + attack)
    gain.gain.exponentialRampToValueAtTime(SILENCE, start + length)
    gain.connect(this.master)
    return gain
  }

  private noiseSource(): AudioBufferSourceNode {
    const source = this.ctx.createBufferSource()
    source.buffer = this.noise
    source.loop = true
    return source
  }

  private createNoise(): AudioBuffer {
    const length = Math.floor(this.ctx.sampleRate * NOISE_SECONDS)
    const buffer = this.ctx.createBuffer(1, length, this.ctx.sampleRate)
    const data = buffer.getChannelData(0)
    for (let i = 0; i < length; i++) data[i] = Math.random() * 2 - 1
    return buffer
  }

  /** Arranca y detiene las fuentes, y las registra para poder cancelarlas. */
  private play(
    start: number,
    end: number,
    sources: Source[],
    envelopes: GainNode[],
    others: AudioNode[],
  ): void {
    for (const source of sources) {
      source.start(start)
      source.stop(end + 0.02)
    }
    this.track(start, sources, envelopes, others)
  }

  private track(
    start: number,
    sources: Source[],
    envelopes: GainNode[],
    others: AudioNode[],
  ): void {
    const entry: Scheduled = { start, sources, envelopes, fading: false }
    this.pending.add(entry)
    sources[0].onended = () => {
      this.pending.delete(entry)
      sources.forEach((s) => s.disconnect())
      ;[...envelopes, ...others].forEach((n) => n.disconnect())
    }
  }
}
