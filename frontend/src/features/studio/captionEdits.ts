import type { CaptionCue, Packaging } from './types'

const same = (a: CaptionCue, b: CaptionCue) => a === b || !!a.source_id && a.source_id === b.source_id
export function editableCues(packaging: Packaging): CaptionCue[] {
  return [...packaging.cues, ...(packaging.untranslated_cues || []).filter(cue => !packaging.cues.some(row => same(row, cue)))]
    .sort((a, b) => a.start - b.start || a.end - b.end)
}
export function captionRetranslation(packaging: Packaging, cue: CaptionCue) {
  const index = packaging.cues.findIndex(row => same(row, cue))
  if (index >= 0) return { index, packaging }
  return { index: packaging.cues.length, packaging: { ...packaging, cues: [...packaging.cues, cue] } }
}
export function correctCaption(packaging: Packaging, cue: CaptionCue, text: string): Packaging {
  const { index, packaging: editable } = captionRetranslation(packaging, cue)
  const missing = packaging.untranslated_cues?.filter(row => !same(row, cue))
  const resolved = missing && missing.length !== packaging.untranslated_cues?.length
  return {
    ...editable,
    cues: editable.cues.map((row, i) => i === index ? { ...row, text, manually_edited: true, emphasis: '' } : row),
    ...(resolved ? { untranslated_cues: missing, translated_rows: (packaging.translation_total_rows || 0) - missing.length,
      translation_status: missing.length ? 'partial' : 'complete' } : {}),
  }
}
