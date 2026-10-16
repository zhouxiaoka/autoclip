/** Human message for a failed API call (FastAPI `detail`, validation array, or error envelope). */
export function errorText(error: unknown) {
  const data = (error as any)?.response?.data
  const detail = data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  // R20 #168: coded refusals send { code, message }.
  if (detail && !Array.isArray(detail) && typeof detail === 'object' && typeof detail.message === 'string' && detail.message.trim()) return detail.message
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
