/** 没有可用的模型：前端用来打开「设置 → 模型」，并换一句带自备密钥说明的文案。 */
export const LLM_NOT_CONFIGURED = 'llm_not_configured'

/**
 * 有 error_code 时以它为准。1.3.2 只留下「没有可用的 LLM 提供商…缺少 API Key」，
 * 那种旧文案也要能点进设置。评分阈值、字幕失败不要算进来。
 */
export function classifyLlmKeyFailure(error?: string | null, code?: string | null): boolean {
  if (code === LLM_NOT_CONFIGURED) return true
  const text = error || ''
  if (!text) return false
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
