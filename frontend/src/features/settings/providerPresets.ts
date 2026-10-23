import raw from '@provider-presets'

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
  sponsor?: { register_url: string; guide_url: string; offer: string; description: string }
  referral: string
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
      }
    : undefined
  const display = row.display_name.trim()
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

export function getCatalog(): ProviderCatalog {
  return catalog
}

export function resolveProviderId(name?: string): string | undefined {
  if (!name) return undefined
  const key = catalog.aliases[name.trim().toLowerCase()] || name.trim().toLowerCase()
  return key in catalog.providers ? key : undefined
}

export function getProvider(name?: string): ProviderPreset | undefined {
  const key = resolveProviderId(name)
  return key ? catalog.providers[key] : undefined
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
