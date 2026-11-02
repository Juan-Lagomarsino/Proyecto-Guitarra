import type { SongAudio, SongDetail } from '../../api/songs'

export type BackingGroup = 'metronome' | 'original' | 'no_guitar' | 'generated'

export interface OptionAvailability {
  /** URL relativa del asset (sin token), si la opción usa audio grabado. */
  url: string | null
  /** Motivo por el que no se puede elegir; `null` si está disponible. */
  disabledReason: string | null
}

const UNAVAILABLE = 'no disponible'

const findAsset = (audio: SongAudio[], kind: string) =>
  audio.find((asset) => asset.kind === kind)

const SEPARATION_REASON: Record<SongDetail['separation_status'], string> = {
  none: UNAVAILABLE,
  // `done` sin asset: la separación terminó pero el archivo no está.
  done: UNAVAILABLE,
  queued: 'separando…',
  running: 'separando…',
  error: 'no se pudo separar',
}

export function originalAvailability(
  song: Pick<SongDetail, 'audio'>,
): OptionAvailability {
  const asset = findAsset(song.audio, 'original')
  return asset
    ? { url: asset.url, disabledReason: null }
    : { url: null, disabledReason: UNAVAILABLE }
}

export function noGuitarAvailability(
  song: Pick<SongDetail, 'audio' | 'separation_status'>,
): OptionAvailability {
  const asset = findAsset(song.audio, 'no_guitar')
  if (asset) return { url: asset.url, disabledReason: null }
  return {
    url: null,
    disabledReason: SEPARATION_REASON[song.separation_status],
  }
}
