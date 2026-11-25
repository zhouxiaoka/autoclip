import raw from '@provider-presets'
import { qualityFor, type LatencyTier, type SuccessTier } from './providerQuality'
import { findDynamicProvider, localizedDynamicText, readDynamicProviders, readPromoLocale, type DynamicProviderSpec } from './sponsorPromoState'

export type ProviderGroupId = 'recommended' | 'popular' | 'local' | 'more'
export type PurposeId = 'analysis' | 'vision' | 'asr' | 'image'

export type ProviderPreset = {
  id: string
  kind: string
  display_name: string
  ui_name: string
  short_name: string
  group: ProviderGroupId
  protocol: string
  base_url: string
  auth: string
  capabilities: string[]
  docs_url: string
  locked: boolean
  accepted_hosts: string[]
  default_model: string
  candidates: Record<PurposeId, string[]>
  openai_compat_remap: boolean
  local_compat_remap: boolean
  legacy_ui: boolean
  api_key_setting: string
  placeholder: string
  hint: string
  context_hint: string
  local_app: string
  sponsor?: { register_url: string; guide_url: string; offer: string; description: string; topup_url?: string }
  referral: string
  icon_url?: string
  dynamic?: boolean
  success_tier?: SuccessTier
  latency_tier?: LatencyTier
  caveat_key?: string
}

export type ProviderCatalog = {
  schema_version: number
  version: number
  issued_at: string
  local_context_hint: string
  console_hosts: string[]
  console_suffixes: string[]
  aliases: Record<string, string>
  providers: Record<string, ProviderPreset>
}

const PURPOSES: PurposeId[] = ['analysis', 'vision', 'asr', 'image']
const GROUPS = new Set<ProviderGroupId>(['recommended', 'popular', 'local', 'more'])

function asStrings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0) : []
}

function parseProvider(id: string, rawProvider: unknown): ProviderPreset | undefined {
  if (!id || !rawProvider || typeof rawProvider !== 'object') return undefined
  const row = rawProvider as Record<string, unknown>
  if (row.kind !== 'preset') return undefined
  if (typeof row.display_name !== 'string' || !row.display_name.trim()) return undefined
  if (typeof row.group !== 'string' || !GROUPS.has(row.group as ProviderGroupId)) return undefined
  if (typeof row.protocol !== 'string' || !row.protocol.trim()) return undefined
  const candidatesRaw = row.candidates && typeof row.candidates === 'object' ? row.candidates as Record<string, unknown> : {}
  const candidates = Object.fromEntries(PURPOSES.map(purpose => [purpose, asStrings(candidatesRaw[purpose])])) as Record<PurposeId, string[]>
  const sponsorRaw = row.sponsor && typeof row.sponsor === 'object' ? row.sponsor as Record<string, unknown> : undefined
  const sponsor = sponsorRaw && ['register_url', 'guide_url', 'offer', 'description'].every(key => typeof sponsorRaw[key] === 'string')
    ? {
        register_url: String(sponsorRaw.register_url),
        guide_url: String(sponsorRaw.guide_url),
        offer: String(sponsorRaw.offer),
        description: String(sponsorRaw.description),
        ...(typeof sponsorRaw.topup_url === 'string' && sponsorRaw.topup_url.trim()
          ? { topup_url: String(sponsorRaw.topup_url).trim() }
          : {}),
      }
    : undefined
  const display = row.display_name.trim()
  const quality = qualityFor(id)
  return {
    id,
    kind: 'preset',
    display_name: display,
    ui_name: String(row.ui_name || display).trim(),
    short_name: String(row.short_name || display).trim(),
    group: row.group as ProviderGroupId,
    protocol: row.protocol.trim(),
    base_url: String(row.base_url || '').trim(),
    auth: String(row.auth || 'api_key').trim(),
    capabilities: asStrings(row.capabilities),
    docs_url: String(row.docs_url || '').trim(),
    locked: Boolean(row.locked),
    accepted_hosts: asStrings(row.accepted_hosts).map(host => host.toLowerCase()),
    default_model: typeof row.default_model === 'string' ? row.default_model : (candidates.analysis[0] || ''),
    candidates,
    openai_compat_remap: Boolean(row.openai_compat_remap),
    local_compat_remap: Boolean(row.local_compat_remap),
    legacy_ui: Boolean(row.legacy_ui),
    api_key_setting: String(row.api_key_setting || `${id}_api_key`),
    placeholder: String(row.placeholder || 'sk-…'),
    hint: String(row.hint || ''),
    context_hint: String(row.context_hint || ''),
    local_app: String(row.local_app || ''),
    sponsor,
    referral: typeof row.referral === 'string' ? row.referral.trim() : '',
    ...(quality ? {
      success_tier: quality.success_tier,
      latency_tier: quality.latency_tier,
      ...(quality.caveat_key ? { caveat_key: quality.caveat_key } : {}),
    } : {}),
  }
}

function parseCatalog(document: unknown): ProviderCatalog {
  if (!document || typeof document !== 'object') throw new Error('provider presets must be an object')
  const data = document as Record<string, unknown>
  if (data.schema_version !== 1) throw new Error(`unsupported provider presets schema_version: ${String(data.schema_version)}`)
  const rawProviders = data.providers && typeof data.providers === 'object' ? data.providers as Record<string, unknown> : {}
  const providers: Record<string, ProviderPreset> = {}
  for (const [id, value] of Object.entries(rawProviders)) {
    const parsed = parseProvider(id, value)
    if (parsed) providers[parsed.id] = parsed
  }
  const aliases: Record<string, string> = {}
  if (data.aliases && typeof data.aliases === 'object') {
    for (const [alias, target] of Object.entries(data.aliases as Record<string, unknown>)) {
      if (typeof target === 'string' && target.trim()) aliases[alias.trim().toLowerCase()] = target.trim()
    }
  }
  const addressRules = (data.address_rules || {}) as Record<string, unknown>
  return {
    schema_version: 1,
    console_hosts: asStrings(addressRules.console_hosts),
    console_suffixes: asStrings(addressRules.console_suffixes),
    version: typeof data.version === 'number' ? data.version : 1,
    issued_at: String(data.issued_at || ''),
    local_context_hint: String(data.local_context_hint || ''),
    aliases,
    providers,
  }
}

const catalog = parseCatalog(raw)

export function dynamicProviderToPreset(spec: DynamicProviderSpec, locale?: string | null): ProviderPreset {
  const loc = locale ?? readPromoLocale()
  const name = localizedDynamicText(spec.name, loc) || spec.id
  const hint = localizedDynamicText(spec.hint, loc)
  const offer = localizedDynamicText(spec.offer, loc)
  let baseHost = ''
  try { baseHost = new URL(spec.baseUrl).hostname.toLowerCase() } catch { baseHost = '' }
  return {
    id: spec.id,
    kind: 'preset',
    display_name: name,
    ui_name: name,
    short_name: name,
    group: spec.group,
    protocol: 'openai-completions',
    base_url: spec.baseUrl,
    auth: 'api_key',
    capabilities: [...spec.capabilities],
    docs_url: spec.docsUrl,
    locked: false,
    accepted_hosts: baseHost ? [baseHost] : [],
    default_model: spec.candidates?.analysis?.[0] || '',
    candidates: {
      analysis: [...(spec.candidates?.analysis || [])],
      vision: [...(spec.candidates?.vision || [])],
      asr: [...(spec.candidates?.asr || [])],
      image: [...(spec.candidates?.image || [])],
    },
    openai_compat_remap: true,
    local_compat_remap: false,
    legacy_ui: false,
    api_key_setting: `${spec.id}_api_key`,
    placeholder: spec.placeholder || 'sk-…',
    hint,
    context_hint: '',
    local_app: '',
    sponsor: {
      register_url: spec.registerUrl,
      guide_url: spec.docsUrl,
      offer,
      description: hint,
    },
    referral: spec.registerUrl,
    ...(spec.iconUrl ? { icon_url: spec.iconUrl } : {}),
    dynamic: true,
  }
}

export function getCatalog(): ProviderCatalog {
  return catalog
}

export function listAllProviders(locale?: string | null): ProviderPreset[] {
  const builtin = Object.values(catalog.providers)
  const dynamic = readDynamicProviders()
    .filter(spec => !(spec.id in catalog.providers))
    .map(spec => dynamicProviderToPreset(spec, locale))
  return [...builtin, ...dynamic]
}

export function resolveProviderId(name?: string): string | undefined {
  if (!name) return undefined
  const normalized = name.trim().toLowerCase()
  const key = catalog.aliases[normalized] || normalized
  if (key in catalog.providers) return key
  if (findDynamicProvider(key)) return key
  return undefined
}

export function getProvider(name?: string, locale?: string | null): ProviderPreset | undefined {
  if (!name) return undefined
  const normalized = name.trim().toLowerCase()
  const key = catalog.aliases[normalized] || normalized
  if (key in catalog.providers) return catalog.providers[key]
  const dynamic = findDynamicProvider(key)
  return dynamic ? dynamicProviderToPreset(dynamic, locale) : undefined
}

export function analysisCandidates(name?: string): string[] {
  return getProvider(name)?.candidates.analysis || []
}

export function visionCandidates(name?: string): string[] {
  return getProvider(name)?.candidates.vision || []
}

export function imageCandidates(name?: string): string[] {
  return getProvider(name)?.candidates.image || []
}

export function asrCandidates(name?: string): string[] {
  return getProvider(name)?.candidates.asr || []
}
