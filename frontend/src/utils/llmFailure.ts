/** 没有可用的模型：前端用来打开「设置 → 模型」，并换一句带自备密钥说明的文案。 */
export const LLM_NOT_CONFIGURED = 'llm_not_configured'
export const LLM_AUTH_INVALID = 'llm_auth_invalid'

/** R27 I424: the lock-timeout notice is an i18n key in all 8 locales (backend file_lock.LOCK_TIMEOUT_MESSAGE). */
export const STORE_LOCK_TIMEOUT = 'store_lock_timeout'
export const STORE_LOCK_TIMEOUT_TEXT = '本机项目数据正被另一个 AutoClip 进程占用，请稍后重试；原素材已保留'

/** The one user-cause reason table (R22): studio 「去设置」 reads it. Project cards only swap llm_auth_invalid. */
export const USER_CAUSE_REASONS: Record<string, string> = {
  authentication: 'API Key 无效或已过期，请到设置里更新后再试',
  llm_auth_invalid: 'API Key 无效或已过期，请到设置里更新后再试',
  invalid_key: 'API Key 无效或已过期，请到设置里更新后再试',
  insufficient_quota: '服务商账户余额不足，请充值或换一个服务商',
  permission_denied: '这个 API Key 没有该模型的使用权限，请到设置里更换',
  llm_not_configured: '还没有配置可用的模型，请先到设置里添加',
}

export function llmFailureText(error?: string | null, code?: string | null): string {
  if (code === STORE_LOCK_TIMEOUT) return STORE_LOCK_TIMEOUT_TEXT
  if (code === LLM_AUTH_INVALID) return USER_CAUSE_REASONS[LLM_AUTH_INVALID]
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
