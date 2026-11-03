/** 时间线为空，且模型连接已经成功。不要打开「设置 → 服务商与模型」或「设置 → 默认模型 → 语音转字幕」。 */
export const TIMELINE_EMPTY = 'timeline_empty'

/**
 * 有 error_code 时以它为准。CLI / 进度条有时只留下 last_error 正文，
 * 那种「时间线提取为空…」也要认出来，避免被当成缺密钥或没字幕。
 */
export function classifyTimelineEmpty(error?: string | null, code?: string | null): boolean {
  if (code === TIMELINE_EMPTY) return true
  const text = error || ''
  if (!text) return false
  return text.includes('时间线提取为空') || text.includes('时间线为空')
}

/** User-facing sentence. Same text as backend WEAK_LOCAL_TIMELINE_REASON. */
export const WEAK_LOCAL_TIMELINE_REASON = '当前本地模型无法返回可用时间线'
/** Stored on failures from before the short sentence. Still this failure, never shown raw. */
const LEGACY_WEAK_MARKER = '经常无法返回可用的时间线'

/** Terminal empty-interval copy, only after the backend has named a weak local model. */
export function weakLocalTimelineFailure(error?: string | null, code?: string | null): boolean {
  if (code && code !== 'invalid_response') return false
  const text = error || ''
  if (text.includes(WEAK_LOCAL_TIMELINE_REASON)) return true
  return text.includes('没有有效时间区间') && text.includes(LEGACY_WEAK_MARKER)
}
