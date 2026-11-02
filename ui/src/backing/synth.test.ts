import { describe, expect, it, vi } from 'vitest'
import { WebAudioVoiceSink } from './synth'

/** AudioContext falso mínimo: registra osciladores y ganancias. */
function fakeContext() {
  const oscillators: ReturnType<typeof makeOsc>[] = []
  const gains: ReturnType<typeof makeGain>[] = []
  const param = () => ({
    value: 0,
    setValueAtTime: vi.fn(),
    linearRampToValueAtTime: vi.fn(),
    exponentialRampToValueAtTime: vi.fn(),
    cancelScheduledValues: vi.fn(),
    setTargetAtTime: vi.fn(),
  })
  const makeNode = () => ({
    connect: vi.fn((next: unknown) => next),
    disconnect: vi.fn(),
  })
  const makeOsc = () => ({
    ...makeNode(),
    type: 'sine',
    frequency: param(),
    start: vi.fn(),
    stop: vi.fn(),
    onended: null as null | (() => void),
  })
  const makeGain = () => ({ ...makeNode(), gain: param() })
  const ctx = {
    currentTime: 0,
    sampleRate: 100,
    destination: makeNode(),
    createOscillator: () => {
      const osc = makeOsc()
      oscillators.push(osc)
      return osc
    },
    createGain: () => {
      const gain = makeGain()
      gains.push(gain)
      return gain
    },
    createBiquadFilter: () => ({ ...makeNode(), type: '', frequency: param() }),
    createBufferSource: () => ({
      ...makeNode(),
      buffer: null,
      loop: false,
      start: vi.fn(),
      stop: vi.fn(),
      onended: null,
    }),
    createBuffer: (_c: number, length: number) => ({
      getChannelData: () => new Float32Array(length),
    }),
  }
  return { ctx, oscillators, gains }
}

const sinkFor = (fake: ReturnType<typeof fakeContext>) =>
  new WebAudioVoiceSink(fake.ctx as unknown as AudioContext)

describe('WebAudioVoiceSink', () => {
  it('un acorde agenda un oscilador por nota', () => {
    const fake = fakeContext()
    sinkFor(fake).trigger('chord', 1, 2, [48, 52, 55], 0.6)
    expect(fake.oscillators).toHaveLength(3)
    fake.oscillators.forEach((o) => expect(o.start).toHaveBeenCalledWith(1))
  })

  it('cancel detiene sin sonar lo que todavía no empezó', () => {
    const fake = fakeContext()
    const sink = sinkFor(fake)
    sink.trigger('bass', 5, 1, 40, 0.8)
    sink.cancel()
    expect(fake.oscillators[0].stop).toHaveBeenLastCalledWith()
  })

  it('cancel hace un fade-out corto de las voces ya empezadas', () => {
    const fake = fakeContext()
    const sink = sinkFor(fake)
    sink.trigger('chord', 0, 4, [48, 52], 0.6)
    fake.ctx.currentTime = 1
    sink.cancel()
    const chordGain = fake.gains[1] // [0] es el master
    expect(chordGain.gain.cancelScheduledValues).toHaveBeenCalledWith(1)
    expect(chordGain.gain.setTargetAtTime).toHaveBeenCalled()
    for (const osc of fake.oscillators) {
      const [stopAt] = osc.stop.mock.calls.at(-1) as [number]
      expect(stopAt).toBeGreaterThan(1)
      expect(stopAt).toBeLessThan(1.1)
    }
    // un segundo cancel no vuelve a tocar lo que ya se está apagando
    sink.cancel()
    expect(chordGain.gain.setTargetAtTime).toHaveBeenCalledTimes(1)
  })

  it('al terminar la fuente se libera el grafo', () => {
    const fake = fakeContext()
    sinkFor(fake).trigger('click', 0, 0.04, undefined, 1)
    const osc = fake.oscillators[0]
    osc.onended?.()
    expect(osc.disconnect).toHaveBeenCalled()
  })
})
