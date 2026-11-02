import type { NoteEvent } from './types'

/** Una nota sin `confidence` (escrita a mano) es siempre confiable. */
export const isLowConfidenceEvent = (
  event: Pick<NoteEvent, 'confidence'>,
  below: number | undefined,
): boolean =>
  below !== undefined &&
  event.confidence !== undefined &&
  event.confidence !== null &&
  event.confidence < below
