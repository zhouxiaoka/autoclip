import { t } from '../../i18n'
import { compareRecommended, pickerBucket, qualityFor, type LatencyTier, type SuccessTier } from './providerQuality'
import { getCatalog, getProvider } from './providerPresets'

export type ProviderKey = 'dashscope' | 'openai' | 'compatible' | 'infistar' | 'api88' | 'apimart' | 'gemini' | 'deepseek' | 'seed' | 'kimi' | 'glm' | 'grok' | 'ollama' | 'lmstudio'
type LocalPreset = { baseUrl: string; defaultModel: string; docsUrl: string; app: string; contextHint: string; success_tier?: SuccessTier; latency_tier?: LatencyTier; caveat_key?: string }
type CloudPreset = { baseUrl: string; defaultModel: string; success_tier?: SuccessTier; latency_tier?: LatencyTier; caveat_key?: string }
export type SponsorId = 'infistar' | 'api88' | 'apimart'
type Sponsor = { id: SponsorId; registerUrl: string; guideUrl: string; offer: string; description: string; topupUrl?: string }
type ProviderGroup = 'sponsor' | 'cloud' | 'compatible' | 'local'
const PROVIDER_GROUPS: Array<{ key: ProviderGroup; label: () => string }> = [
  { key: 'sponsor', label: () => t('推荐') },
  { key: 'cloud', label: () => t("官方供应商") },
  { key: 'compatible', label: () => t("兼容接口") },
  { key: 'local', label: () => t("本机运行") },
]

type ProviderEntry = { name: string; short: string; hint: string; apiKeyField: string; placeholder: string; keyUrl: string; group: ProviderGroup; success_tier?: SuccessTier; latency_tier?: LatencyTier; caveat_key?: string; local?: LocalPreset; cloud?: CloudPreset; sponsor?: Sponsor; referralUrl?: string }

function measuredFields(id: string): { success_tier?: SuccessTier; latency_tier?: LatencyTier; caveat_key?: string } {
  const row = qualityFor(id)
  if (!row) return {}
  return {
    success_tier: row.success_tier,
    latency_tier: row.latency_tier,
    ...(row.caveat_key ? { caveat_key: row.caveat_key } : {}),
  }
}

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
  const measured = measuredFields(key)
  if (measured.success_tier) entry.success_tier = measured.success_tier
  if (measured.latency_tier) entry.latency_tier = measured.latency_tier
  if (measured.caveat_key) entry.caveat_key = measured.caveat_key
  if (row.openai_compat_remap) entry.cloud = { baseUrl: row.base_url, defaultModel: row.default_model, ...measured }
  if (row.local_compat_remap) {
    entry.local = {
      baseUrl: row.base_url,
      defaultModel: row.default_model,
      docsUrl: row.docs_url,
      app: row.local_app || row.short_name,
      get contextHint() { return t(row.context_hint) },
      ...measured,
    }
  }
  if (row.sponsor && (key === 'api88' || key === 'infistar' || key === 'apimart')) {
    entry.sponsor = {
      id: key,
      registerUrl: row.sponsor.register_url,
      guideUrl: row.sponsor.guide_url,
      get offer() { return t(row.sponsor!.offer) },
      get description() { return t(row.sponsor!.description) },
      ...(row.sponsor.topup_url ? { topupUrl: row.sponsor.topup_url } : {}),
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
      ...measuredFields('compatible'),
      apiKeyField: 'openai_api_key',
      get placeholder() { return t('sk-…（自建服务可留空）') },
      keyUrl: '',
    }
    return acc
  }
  acc[key] = fromPreset(key)
  return acc
}, {} as Record<ProviderKey, ProviderEntry>)

function recommendedCompare(a: ProviderKey, b: ProviderKey): number {
  return compareRecommended(
    { sponsor: PROVIDERS[a].sponsor, success_tier: PROVIDERS[a].success_tier, success_rate: qualityFor(a)?.success_rate },
    { sponsor: PROVIDERS[b].sponsor, success_tier: PROVIDERS[b].success_tier, success_rate: qualityFor(b)?.success_rate },
  )
}

/** Sponsors stay first. High/mid official providers follow by success tier. Low tiers stay in 官方供应商. */
export function recommendedSetupProviders(): ProviderKey[] {
  return (Object.keys(PROVIDERS) as ProviderKey[])
    .filter(key => pickerBucket(PROVIDERS[key].group, PROVIDERS[key].success_tier) === 'sponsor')
    .sort(recommendedCompare)
}

export const providerPickerOptions = () => PROVIDER_GROUPS
  .map((group) => ({
    label: group.label(),
    options: (Object.keys(PROVIDERS) as ProviderKey[])
      .filter((key) => {
        if (pickerBucket(PROVIDERS[key].group, PROVIDERS[key].success_tier) !== group.key) return false
        if (key === 'compatible') return true
        const preset = getProvider(key)
        return !preset || !!preset.base_url.trim() || !!PROVIDERS[key].local
      })
      .sort((a, b) => group.key === 'sponsor' ? recommendedCompare(a, b) : 0)
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

/** Local servers usually start with a small context; long transcripts need >= 16384 (RC156 Win QA #14b).
 * T3: when params_b / context_tokens are known, prefer a concrete floor message.
 */
export const contextHintFor = (
  key: ProviderKey | undefined,
  baseUrl?: string,
  size?: { params_b?: number | null; context_tokens?: number | null; id?: string } | null,
) => {
  if (!key) return ''
  const local = PROVIDERS[key].local
  if (local || (key === 'compatible' && isLocalAddress(baseUrl))) {
    const params = size?.params_b
    const context = size?.context_tokens
    if (typeof params === 'number' || typeof context === 'number') {
      const bits: string[] = []
      if (typeof params === 'number') bits.push(`${params}B`)
      if (typeof context === 'number') bits.push(`${context >= 1024 ? Math.round(context / 1024) + 'k' : context} ctx`)
      if ((typeof params === 'number' && params < 7) || (typeof context === 'number' && context < 8192)) {
        return t('当前型号 {{size}}，大概率解析失败，不建议做分析。建议 ≥7B 且上下文 ≥8k。', { size: bits.join(' / ') })
      }
      return t('当前型号 {{size}}。分析建议 ≥7B 且上下文 ≥8k。', { size: bits.join(' / ') })
    }
    if (local) return local.contextHint
    return t(getCatalog().local_context_hint)
  }
  return ''
}
