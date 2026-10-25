import { t } from '../../i18n'
import {
  hintKeyForUpstreamError,
  hostnameOfBaseUrl,
  UPSTREAM_ERROR_TYPES,
} from '../../analytics/successRateContract'
import { PROVIDERS, type ProviderKey } from './providers'
import { getCatalog } from './providerPresets'
import { cleanupBaseUrl, normalizeProviderUrl } from './providerUrl'

const catalog = getCatalog()
export const ADDRESS_LOCKED = Object.values(catalog.providers).filter(row => row.locked && row.base_url).map(row => row.id)

export const VALIDATION_ERROR_TYPES = UPSTREAM_ERROR_TYPES
export type ValidationErrorType = (typeof VALIDATION_ERROR_TYPES)[number]
export type ValidationStatus = 'ok' | 'failed' | 'unchecked' | 'transient'

export interface ValidationResult {
  success?: boolean
  ok?: boolean
  result?: 'ok' | 'failed' | 'success' | 'transient'
  error_type?: string
  hint_key?: string
  key_hint?: string | null
  normalized_base_url?: string
  base_url_host?: string
  models?: string[]
  recommended?: Record<string, string[]>
  truncated?: boolean
  message_key?: string
  /** 1.5.7 telemetry: closed-set connection-test code and integer upstream status. */
  error_code?: string
  http_status?: number | null
  config_source?: 'preset' | 'customized'
}

const KEY_HINTS: Array<[RegExp, ProviderKey]> = [
  [/^AIza/, 'gemini'],
  [/^xai-/, 'grok'],
  [/^sk-proj-/, 'openai'],
  [/^sk-svcacct-/, 'openai'],
  [/^sk-or-/, 'compatible'],
  [/^sk-ant-/, 'compatible'],
]

const CONSOLE_COPY = '这是控制台或官网地址，不是模型接口。请改选对应服务商，或用「自定义兼容」填写带 /v1 的接口地址。'
export const VISION_UNSUPPORTED = 'vision_unsupported'
export const VISION_HINT_KEY = '画面理解使用的模型不能看图。设置已保存，开始生成前会拦住。请到「设置 → 服务商与模型」换一个能看图的模型。'
export const VISION_BLOCK_MESSAGE = '画面理解使用的模型不能看图。请到「设置 → 服务商与模型」换一个能看图的模型后再生成。'

/** Locked presets still show the official default and allow overrides (接口地址). */
export const canEditAddress = (key?: string) => {
  if (!key) return false
  if (key === 'compatible') return true
  const preset = catalog.providers[key]
  if (!preset) return false
  if (preset.protocol === 'local' && !preset.base_url) return false
  return true
}

export function hintProviderForKey(apiKey?: string | null): ProviderKey | null {
  const key = (apiKey || '').trim()
  for (const [pattern, provider] of KEY_HINTS) {
    if (pattern.test(key)) return provider
  }
  return null
}

export function isConsoleHost(host?: string) {
  const value = (host || '').toLowerCase().replace(/^\.+|\.+$/g, '')
  if (!value) return false
  const current = getCatalog()
  // Match the backend: catalog API and accepted legacy hosts take precedence.
  for (const preset of Object.values(current.providers)) {
    if (preset.accepted_hosts.includes(value)) return false
    try { if (new URL(preset.base_url).hostname.toLowerCase() === value) return false } catch { /* No API host. */ }
  }
  return current.console_hosts.includes(value) || current.console_suffixes.some(suffix => value.endsWith(suffix))
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
  if (errorType === VISION_UNSUPPORTED) return t(hintKey || VISION_HINT_KEY)
  return t(hintKey || hintKeyForUpstreamError(errorType || 'unknown'))
}

export function keyHintCopy(hint: ProviderKey) {
  return t('此 key 看起来属于 {{name}}。当前仍使用你选择的服务商，不会自动改。', { name: PROVIDERS[hint]?.name || hint })
}

export function sponsorKeyLink(provider?: string): { label: string; href: string } | null {
  if (provider === 'api88') return { label: t('去 88API 获取密钥'), href: PROVIDERS.api88.keyUrl }
  if (provider === 'infistar') return { label: t('去 Infistar 获取密钥'), href: PROVIDERS.infistar.keyUrl }
  if (provider === 'apimart') return { label: t('去 APIMart 获取密钥'), href: PROVIDERS.apimart.keyUrl }
  return null
}

export function passed(result?: ValidationResult | null) {
  return !!(result && (result.success || result.ok || result.result === 'ok' || result.result === 'success'))
}
