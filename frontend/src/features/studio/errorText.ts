export const ERROR_CODE_TEXT: Record<string, string> = {
  append_platform_unavailable: '这一版还不能追加平台，请新建一个项目',
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
