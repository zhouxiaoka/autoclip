export const ERROR_CODE_TEXT: Record<string, string> = {
  append_platform_unavailable: '这一版还不能追加平台，请新建一个项目',
}

/** Human message for a failed API call (FastAPI `detail`, validation array, or error envelope). */
export function errorText(error: unknown) {
  const data = (error as any)?.response?.data
  const detail = data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  // Coded refusal: { error_code } picks the stable copy; { code, message } (the import gate) keeps the backend message.
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const coded = typeof detail.error_code === 'string' ? ERROR_CODE_TEXT[detail.error_code] : undefined
    if (coded) return coded
    if (typeof detail.message === 'string' && detail.message.trim()) return detail.message
    if (typeof detail.error_code === 'string') return '请求失败，请重试'
  }
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

/** Stable machine code of a coded 422 ({ detail: { code } }), or undefined. Never derived from message text. */
export function errorCode(error: unknown): string | undefined {
  const detail = (error as any)?.response?.data?.detail
  return detail && !Array.isArray(detail) && typeof detail === 'object' && typeof detail.code === 'string' ? detail.code : undefined
}
