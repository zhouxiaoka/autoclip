import { t } from '../../i18n'
import { PROVIDERS, type ProviderKey } from './providers'

export const ADDRESS_LOCKED: readonly ProviderKey[] = ['api88', 'infistar', 'deepseek', 'gemini', 'dashscope', 'openai']

export const VALIDATION_ERROR_TYPES = [
  'insufficient_quota', 'invalid_key', 'model_forbidden', 'group_forbidden',
  'model_not_found', 'rate_limited', 'upstream_unavailable',
  'bad_endpoint', 'console_host', 'connection', 'timeout', 'unknown',
] as const

export type ValidationErrorType = (typeof VALIDATION_ERROR_TYPES)[number]
export type ValidationStatus = 'ok' | 'failed' | 'unchecked'

export interface ValidationResult {
  success?: boolean
  ok?: boolean
  result?: 'ok' | 'failed'
  error_type?: string
  key_hint?: string | null
  normalized_base_url?: string
  base_url_host?: string
  models?: string[]
}

const KEY_HINTS: Array<[RegExp, ProviderKey]> = [
  [/^AIza/, 'gemini'],
  [/^xai-/, 'grok'],
  [/^sk-proj-/, 'openai'],
  [/^sk-svcacct-/, 'openai'],
  [/^sk-or-/, 'compatible'],
  [/^sk-ant-/, 'compatible'],
]

const VERSIONED = /^\/(?:v\d+(?:beta)?(?:\/openai)?|compatible-mode\/v\d+|api\/v\d+|api\/paas\/v\d+|openai\/v\d+)\/?$/i
const CHAT_SUFFIXES = ['/v1/chat/completions', '/chat/completions', '/v1/completions', '/completions']
const CONSOLE_HOSTS = new Set([
  'platform.openai.com', 'chatgpt.com', 'openai.com', 'www.openai.com',
  'platform.deepseek.com', 'chat.deepseek.com', 'www.deepseek.com', 'deepseek.com',
  'aistudio.google.com', 'ai.google.dev', 'makersuite.google.com',
  'console.cloud.google.com', 'bailian.console.aliyun.com', 'dashscope.console.aliyun.com',
  'www.aliyun.com', 'aliyun.com', 'console.volcengine.com', 'www.volcengine.com',
  'platform.moonshot.cn', 'www.moonshot.cn', 'console.x.ai',
  'www.infistar.cc', 'www.infistar.ai', 'infistar.ai', 'www.88api.ai',
])

export const VALIDATION_COPY: Record<string, string> = {
  console_host: '这是控制台或官网地址，不是模型接口。请改选对应服务商，或用「自定义兼容」填写带 /v1 的接口地址。',
  bad_endpoint: '接口地址不对。请检查是否漏了 /v1，或误把 /chat/completions、控制台域名当成接口。',
  invalid_key: '密钥无效。请到「设置 → 模型」核对 API Key，或到服务商网站重新创建。',
  insufficient_quota: '余额或额度不足。请到服务商控制台充值或更换令牌后再试。',
  model_forbidden: '当前密钥没有这个模型的权限。请到令牌设置里勾选该模型，或换一个模型。',
  group_forbidden: '当前密钥不能访问这个分组。请到服务商控制台调整分组，或换一把令牌。',
  model_not_found: '当前分组下没有这个模型。请换一个模型，或到服务商控制台调整分组。',
  rate_limited: '提供商限制了请求频率或额度，请检查配额并稍后重试。',
  connection: '无法连接模型服务。请检查接口地址和网络。',
  timeout: '模型服务响应超时。请稍后重试，或检查网络。',
  upstream_unavailable: '服务商暂时不可用。请稍后重试。',
  unknown: '连接未通过校验。请按提示修改后，到「设置 → 模型」再保存一次。',
}

export const canEditAddress = (key?: ProviderKey) => key === 'compatible' || !!PROVIDERS[key || 'compatible']?.local

export function hintProviderForKey(apiKey?: string | null): ProviderKey | null {
  const key = (apiKey || '').trim()
  for (const [pattern, provider] of KEY_HINTS) {
    if (pattern.test(key)) return provider
  }
  return null
}

export function isConsoleHost(host?: string) {
  const value = (host || '').toLowerCase().replace(/^\.+|\.+$/g, '')
  return CONSOLE_HOSTS.has(value) || value.endsWith('.console.aliyun.com') || value.endsWith('.console.volcengine.com')
}

export function normalizeCompatibleUrl(raw: string): { url: string; warnings: string[] } {
  let url = (raw || '').replace(/\s+/g, '').trim().replace(/\/+$/, '')
  const warnings: string[] = []
  let host = ''
  try { host = new URL(url).hostname.toLowerCase() } catch { return { url, warnings } }
  if (isConsoleHost(host)) return { url, warnings: ['console_host'] }
  const lower = url.toLowerCase()
  for (const suffix of CHAT_SUFFIXES) {
    if (lower.endsWith(suffix)) {
      url = url.slice(0, url.length - suffix.length).replace(/\/+$/, '')
      warnings.push('chat_completions')
      break
    }
  }
  let path = ''
  try { path = new URL(url).pathname || '' } catch { return { url, warnings } }
  if (!VERSIONED.test(path)) {
    url = url.replace(/\/+$/, '') + '/v1'
    warnings.push('missing_v1')
  }
  return { url, warnings }
}

export function telemetryHost(url?: string) {
  if (!url) return 'unknown'
  try {
    const host = new URL(url).hostname.toLowerCase()
    if (['localhost', '127.0.0.1', '0.0.0.0', '::1'].includes(host) || host.endsWith('.local')) return 'local'
    if (/^[a-z0-9.-]{1,253}$/.test(host)) return host
  } catch { /* ignore */ }
  return 'unknown'
}

export function validationCopy(errorType?: string) {
  return t(VALIDATION_COPY[errorType || ''] || VALIDATION_COPY.unknown)
}

export function keyHintCopy(hint: ProviderKey) {
  return t('此 key 看起来属于 {{name}}。当前仍使用你选择的服务商，不会自动改。', { name: PROVIDERS[hint]?.name || hint })
}

export function sponsorKeyLink(provider?: string): { label: string; href: string } | null {
  if (provider === 'api88') return { label: t('去 88API 获取密钥'), href: PROVIDERS.api88.keyUrl }
  if (provider === 'infistar') return { label: t('去 Infistar 获取密钥'), href: PROVIDERS.infistar.keyUrl }
  return null
}

export function passed(result?: ValidationResult | null) {
  return !!(result && (result.success || result.ok || result.result === 'ok'))
}
