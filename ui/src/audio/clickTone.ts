export const ACCENT_HZ = 1500
export const NORMAL_HZ = 1000
export const CLICK_SECONDS = 0.04
export const CLICK_GAIN = 0.4
const SILENCE = 0.001

export interface ClickTone {
  osc: OscillatorNode
  gain: GainNode
}

/** Clic de metrónomo: seno corto con caída exponencial, ya agendado en `start`. */
export function playClickTone(
  ctx: AudioContext,
  destination: AudioNode,
  start: number,
  accent: boolean,
): ClickTone {
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.frequency.value = accent ? ACCENT_HZ : NORMAL_HZ
  gain.gain.setValueAtTime(CLICK_GAIN, start)
  gain.gain.exponentialRampToValueAtTime(SILENCE, start + CLICK_SECONDS)
  osc.connect(gain).connect(destination)
  osc.start(start)
  osc.stop(start + CLICK_SECONDS)
  return { osc, gain }
}
