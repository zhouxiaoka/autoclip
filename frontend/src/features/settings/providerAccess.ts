import { t } from '../../i18n'
import {
  hintKeyForUpstreamError,
  hostnameOfBaseUrl,
  UPSTREAM_ERROR_TYPES,
} from '../../analytics/successRateContract'
import { PROVIDERS, type ProviderKey } from './providers'
import { cleanupBaseUrl, normalizeProviderUrl } from './providerUrl'

export const ADDRESS_LOCKED: readonly ProviderKey[] = ['api88', 'infistar', 'deepseek', 'gemini', 'dashscope', 'openai']

export const VALIDATION_ERROR_TYPES = UPSTREAM_ERROR_TYPES
export type ValidationErrorType = (typeof VALIDATION_ERROR_TYPES)[number]
export type ValidationStatus = 'ok' | 'failed' | 'unchecked'

export interface ValidationResult {
  success?: boolean
  ok?: boolean
  result?: 'ok' | 'failed' | 'success'
  error_type?: string
  hint_key?: string
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

const CONSOLE_HOSTS = new Set([
  'platform.openai.com', 'chatgpt.com', 'openai.com', 'www.openai.com',
  'platform.deepseek.com', 'chat.deepseek.com', 'www.deepseek.com', 'deepseek.com',
  'aistudio.google.com', 'ai.google.dev', 'makersuite.google.com',
  'console.cloud.google.com', 'bailian.console.aliyun.com', 'dashscope.console.aliyun.com',
  'www.aliyun.com', 'aliyun.com', 'console.volcengine.com', 'www.volcengine.com',
  'platform.moonshot.cn', 'www.moonshot.cn', 'console.x.ai',
  'www.infistar.cc', 'www.infistar.ai', 'infistar.ai', 'www.88api.ai',
])
const CONSOLE_COPY = '这是控制台或官网地址，不是模型接口。请改选对应服务商，或用「自定义兼容」填写带 /v1 的接口地址。'

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

export function normalizeCompatibleUrl(raw: string, provider = 'compatible'): { url: string; warnings: string[] } {
  const warnings: string[] = []
  const cleaned = cleanupBaseUrl(raw)
  if (!cleaned) return { url: '', warnings }
  let host = ''
  try { host = new URL(cleaned).hostname.toLowerCase() } catch { return { url: cleaned, warnings } }
  if (isConsoleHost(host)) return { url: cleaned, warnings: ['console_host'] }
  return normalizeProviderUrl(cleaned, provider)
}

export function telemetryHost(url?: string) {
  return hostnameOfBaseUrl(url) || 'unknown'
}

export function validationCopy(errorType?: string, hintKey?: string) {
  if (errorType === 'console_host') return t(CONSOLE_COPY)
  return t(hintKey || hintKeyForUpstreamError(errorType || 'unknown'))
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
  return !!(result && (result.success || result.ok || result.result === 'ok' || result.result === 'success'))
}
