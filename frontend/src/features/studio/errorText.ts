export const ERROR_CODE_TEXT: Record<string, string> = {
  append_platform_exists: '该平台已有版本',
  append_no_auto_output: '没有可自动生成的平台版本',
  append_retry_pending: '请先确认待处理的重试',
  append_attempt_running: '上一次制作还没结束，请稍后再追加平台',
}

/** Human message for a failed API call (FastAPI `detail`, validation array, or error envelope). */
export function errorText(error: unknown) {
  const data = (error as any)?.response?.data
  const detail = data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  // R30: a coded refusal - the stable code picks the copy (callers translate it with t), else the backend message
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) return ERROR_CODE_TEXT[detail.error_code] || detail.message || '请求失败，请重试'
  // F2: a validation array carries the specific field hint — prefer it over the generic envelope.
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0]
    if (typeof first === 'string' && first.trim()) return first
    const msg = first?.msg || first?.message
    if (typeof msg === 'string' && msg.trim()) return msg
  }
  const envelope = data?.error?.message || data?.error?.user_message
  if (typeof envelope === 'string' && envelope.trim()) return envelope
  return (error as Error)?.message || '请求失败，请重试'
}
