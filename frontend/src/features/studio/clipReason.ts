const FRAMING_KEYS: Record<string, string> = {
  speaker: '已按说话人重新取景',
  full_frame: '画面里没有可跟随的人物，保留完整画面',
  full_frame_pending: '人物识别组件准备中，这条先保留完整画面',
  full_frame_captions: '原片自带字幕，保留完整画面以免裁掉字幕',
}

export type ClipReason = { kind: 'evidence'; evidence: string } | { kind: 'framing' | 'content'; key: string }

/** One local line for a card. The sentence stays on the device and is never an event property. */
export function clipReason(input: { evidence?: string | null; framing?: string | null }): ClipReason {
  const evidence = (input.evidence || '').replace(/\s+/g, ' ').trim()
  if (evidence) return { kind: 'evidence', evidence }
  const framing = input.framing && FRAMING_KEYS[input.framing]
  if (framing) return { kind: 'framing', key: framing }
  return { kind: 'content', key: '按内容完整度选出这段' }
}
