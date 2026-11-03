import type { Draft } from './types'

/**
 * the one subtitle state the rendered video actually uses. Template packaging
 * has its own captions switch (#367); preview, export confirm and `subtitle_enabled`
 * telemetry must all read this instead of `draft.subtitles` alone.
 */
export function effectiveSubtitles(draft?: Pick<Partial<Draft>, 'subtitles' | 'packaging'> | null): boolean {
  if (!draft) return false
  // match the backend render — with template packaging, only packaging.captions_enabled
  // decides the burned captions (draft.subtitles drives the legacy subtitle path only).
  if (draft.packaging) return draft.packaging.captions_enabled !== false
  return draft.subtitles === true
}
