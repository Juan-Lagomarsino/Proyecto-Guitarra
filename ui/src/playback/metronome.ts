import type { ClickSink, Clock } from './clock'
import { isDownbeat } from './timing'

const TICK_MS = 25
const LOOKAHEAD_SECONDS = 0.1

/**
 * Metrónomo con programación anticipada. No lleva tiempo propio: pregunta
 * en qué instante del reloj cae cada beat (`timeOfBeat`), que define el
 * transporte. Así los clics quedan sincronizados con la reproducción y
 * siguen los cambios de BPM.
 */
export class Metronome {
  private stopTimer: (() => void) | null = null
  private nextBeat = 0

  constructor(
    private readonly clock: Clock,
    private readonly sink: ClickSink,
    private readonly barLength: number,
  ) {}

  start(
    timeOfBeat: (beat: number) => number,
    firstBeat: number,
    shouldClick: (beat: number) => boolean,
  ): void {
    this.stop()
    this.nextBeat = Math.ceil(firstBeat - 1e-9) + 0 // + 0 evita -0
    const schedule = () => {
      const horizon = this.clock.now() + LOOKAHEAD_SECONDS
      while (timeOfBeat(this.nextBeat) < horizon) {
        if (shouldClick(this.nextBeat)) {
          this.sink.click(
            timeOfBeat(this.nextBeat),
            isDownbeat(this.nextBeat, this.barLength),
          )
        }
        this.nextBeat++
      }
    }
    schedule()
    this.stopTimer = this.clock.every(schedule, TICK_MS)
  }

  stop(): void {
    this.stopTimer?.()
    this.stopTimer = null
    this.sink.cancel()
  }
}
