import { t } from '../../i18n'
import { getCatalog, getProvider } from './providerPresets'

export type ProviderKey = 'dashscope' | 'openai' | 'compatible' | 'infistar' | 'api88' | 'apimart' | 'gemini' | 'deepseek' | 'seed' | 'kimi' | 'glm' | 'grok' | 'ollama' | 'lmstudio'
type LocalPreset = { baseUrl: string; defaultModel: string; docsUrl: string; app: string; contextHint: string }
type CloudPreset = { baseUrl: string; defaultModel: string }
export type SponsorId = 'infistar' | 'api88' | 'apimart'
type Sponsor = { id: SponsorId; registerUrl: string; guideUrl: string; offer: string; description: string }
type ProviderGroup = 'sponsor' | 'cloud' | 'compatible' | 'local'
const PROVIDER_GROUPS: Array<{ key: ProviderGroup; label: () => string }> = [
  { key: 'sponsor', label: () => t('推荐') },
  { key: 'cloud', label: () => t("官方供应商") },
  { key: 'compatible', label: () => t("兼容接口") },
  { key: 'local', label: () => t("本机运行") },
]

type ProviderEntry = { name: string; short: string; hint: string; apiKeyField: string; placeholder: string; keyUrl: string; group: ProviderGroup; local?: LocalPreset; cloud?: CloudPreset; sponsor?: Sponsor; referralUrl?: string }

const UI_KEYS: ProviderKey[] = [
  'dashscope', 'openai', 'compatible', 'api88', 'infistar', 'apimart',
  'gemini', 'deepseek', 'seed', 'kimi', 'glm', 'grok',
  'ollama', 'lmstudio',
]

function groupFor(key: ProviderKey): ProviderGroup {
  if (key === 'compatible') return 'compatible'
  if (key === 'api88' || key === 'infistar' || key === 'apimart') return 'sponsor'
  if (key === 'ollama' || key === 'lmstudio') return 'local'
  return 'cloud'
}

function fromPreset(key: Exclude<ProviderKey, 'compatible'>): ProviderEntry {
  const row = getProvider(key)
  if (!row) throw new Error(`missing provider preset: ${key}`)
  const entry: ProviderEntry = {
    get name() { return t(row.ui_name) },
    get short() { return t(row.short_name) },
    get hint() { return t(row.hint) },
    apiKeyField: row.api_key_setting,
    placeholder: row.placeholder,
    keyUrl: row.docs_url,
    group: groupFor(key),
    referralUrl: row.referral || '',
  }
  if (row.openai_compat_remap) entry.cloud = { baseUrl: row.base_url, defaultModel: row.default_model }
  if (row.local_compat_remap) {
    entry.local = {
      baseUrl: row.base_url,
      defaultModel: row.default_model,
      docsUrl: row.docs_url,
      app: row.local_app || row.short_name,
      get contextHint() { return t(row.context_hint) },
    }
  }
  if (row.sponsor && (key === 'api88' || key === 'infistar' || key === 'apimart')) {
    entry.sponsor = {
      id: key,
      registerUrl: row.sponsor.register_url,
      guideUrl: row.sponsor.guide_url,
      get offer() { return t(row.sponsor!.offer) },
      get description() { return t(row.sponsor!.description) },
    }
  }
  return entry
}

export const PROVIDERS: Record<ProviderKey, ProviderEntry> = UI_KEYS.reduce((acc, key) => {
  if (key === 'compatible') {
    acc.compatible = {
      get name() { return t('自定义 OpenAI 兼容接口') },
      get short() { return t('自定义兼容接口') },
      get hint() { return t('适用于 OpenRouter、第三方网关或自建服务。') },
      group: 'compatible',
      apiKeyField: 'openai_api_key',
      get placeholder() { return t('sk-…（自建服务可留空）') },
      keyUrl: '',
    }
    return acc
  }
  acc[key] = fromPreset(key)
  return acc
}, {} as Record<ProviderKey, ProviderEntry>)

export const providerPickerOptions = () => PROVIDER_GROUPS
  .map((group) => ({
    label: group.label(),
    options: (Object.keys(PROVIDERS) as ProviderKey[])
      .filter((key) => {
        if (PROVIDERS[key].group !== group.key) return false
        if (key === 'compatible') return true
        const preset = getProvider(key)
        return !preset || !!preset.base_url.trim() || !!PROVIDERS[key].local
      })
      .map((key) => ({
        value: key,
        label: PROVIDERS[key].short,
        search: `${key} ${PROVIDERS[key].short} ${PROVIDERS[key].name}`.toLowerCase(),
        title: PROVIDERS[key].name,
      })),
  }))
  .filter((group) => group.options.length)

/** Same rule as backend `is_local_url`: loopback, private / link-local IPs, localhost and *.local hosts. */
export const isLocalAddress = (url?: string) => {
  let host = ''
  try { host = new URL((url || '').trim()).hostname.toLowerCase().replace(/^\[|\]$/g, '') } catch { return false }
  if (['localhost', '0.0.0.0', 'host.docker.internal', '::1'].includes(host) || host.endsWith('.local') || host.endsWith('.localhost')) return true
  const v4 = host.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)$/)
  if (!v4) return /^f[cd][0-9a-f]{2}:|^fe80:/.test(host)
  const [a, b] = [Number(v4[1]), Number(v4[2])]
  return a === 127 || a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 169 && b === 254)
}

/** Local servers usually start with a small context; long transcripts need >= 16384 (RC156 Win QA #14b). */
export const contextHintFor = (key: ProviderKey | undefined, baseUrl?: string) => {
  if (!key) return ''
  const local = PROVIDERS[key].local
  if (local) return local.contextHint
  if (key === 'compatible' && isLocalAddress(baseUrl)) return t(getCatalog().local_context_hint)
  return ''
}
