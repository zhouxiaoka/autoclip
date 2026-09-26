/** 时间线为空，且模型连接已经成功。不要打开「设置 → 模型」或「设置 → 转写」。 */
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
