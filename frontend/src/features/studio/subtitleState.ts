import type { Draft } from './types'

/**
 * R10 #396: the one subtitle state the rendered video actually uses. Template packaging
 * has its own captions switch (#367); preview, export confirm and `subtitle_enabled`
 * telemetry must all read this instead of `draft.subtitles` alone.
 */
export function effectiveSubtitles(draft?: Pick<Partial<Draft>, 'subtitles' | 'packaging'> | null): boolean {
  if (!draft || draft.subtitles === false || !draft.subtitles) return false
  return draft.packaging?.captions_enabled !== false
}
