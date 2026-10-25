import { USER_CAUSE_ERROR_CODES, USER_CAUSE_UPSTREAM_TYPES, USER_MESSAGES } from '../analytics/failureCodes'

/** 没有可用的模型：前端用来打开「设置 → 服务商与模型」，并换一句带自备密钥说明的文案。 */
export const LLM_NOT_CONFIGURED = 'llm_not_configured'
export const LLM_AUTH_INVALID = 'llm_auth_invalid'

/** the lock-timeout notice is an i18n key in all 8 locales (backend file_lock.LOCK_TIMEOUT_MESSAGE).*/
export const STORE_LOCK_TIMEOUT = 'store_lock_timeout'
export const STORE_LOCK_TIMEOUT_TEXT = '本机项目数据正被另一个 AutoClip 进程占用，请稍后重试；原素材已保留'

/** The one user-cause reason table studio 「去设置」 reads it. Project cards only swap llm_auth_invalid.*/
export const USER_CAUSE_REASONS: Record<string, string> = Object.fromEntries(
  [...new Set([...USER_CAUSE_ERROR_CODES, ...USER_CAUSE_UPSTREAM_TYPES])].map(code => [code, USER_MESSAGES[code]]),
)

export function llmFailureText(error?: string | null, code?: string | null, upstream?: string | null): string {
  if (code === STORE_LOCK_TIMEOUT) return STORE_LOCK_TIMEOUT_TEXT
  if (code === LLM_AUTH_INVALID) return USER_CAUSE_REASONS[LLM_AUTH_INVALID]
  // Coarse provider_error / unexpected still say 「无法识别」 or 「请重试」. The fine type already
  // has a sentence; use it when the stored text is that generic fallback (or empty).
  const generic = !error || error === USER_MESSAGES.provider_error || error === USER_MESSAGES.unexpected || error === USER_MESSAGES.unknown
  if (generic && upstream && upstream !== 'unknown' && USER_MESSAGES[upstream]) return USER_MESSAGES[upstream]
  return error || ''
}

/**
 * 有 error_code 时以它为准。1.3.2 只留下「没有可用的 LLM 提供商…缺少 API Key」，
 * 那种旧文案也要能点进设置。评分阈值、字幕失败、时间线为空不要算进来。
 */
export function classifyLlmKeyFailure(error?: string | null, code?: string | null): boolean {
  if (code === LLM_NOT_CONFIGURED) return true
  if (code === 'timeline_empty' || code === LLM_AUTH_INVALID) return false
  const text = error || ''
  if (!text) return false
  if (text.includes('时间线提取为空') || text.includes('时间线为空')) return false
  if (text.includes('最低评分')) return false
  if (
    text.includes('没有可用的 LLM')
    || text.includes('缺少 API Key')
    || text.includes('未配置LLM')
    || text.includes('未配置 API Key')
    || text.includes('需要自备 API Key')
    || text.includes('自备密钥')
  ) {
    return true
  }
  const mentionsKey = /API Key|API key|密钥/.test(text)
  return mentionsKey && (text.includes('连接测试失败') || text.includes('API连接测试失败'))
}
