/**
 * Accepted promotion snapshot. No provider imports, so pickers and failure actions can read it
 * without a cycle. Empty until a watcher publishes a validated view.
 */
export interface LocalePromoSlice {
  choices: string[]
  defaultChoice: string
  registerUrls: Record<string, string>
  firstRunChoices?: string[]
  firstRunDefault?: string
}

export interface DynamicProviderSpec {
  id: string
  name: Record<string, string>
  baseUrl: string
  registerUrl: string
  docsUrl: string
  placeholder: string
  capabilities: string[]
  group: 'popular' | 'recommended'
  hint?: Record<string, string>
  offer?: Record<string, string>
  iconUrl?: string
  candidates?: Partial<Record<'analysis' | 'vision' | 'asr' | 'image', string[]>>
  locales?: string[]
}

export interface PromoSnapshot {
  choices: string[]
  defaultChoice: string
  firstRunChoices?: string[]
  firstRunDefault?: string
  statuses: Record<string, string>
  registerUrls: Record<string, string>
  notices: Record<string, Record<string, string>>
  badges?: Record<string, string | Record<string, string>>
  byLocale?: Record<string, LocalePromoSlice>
  providers?: DynamicProviderSpec[]
  sequence?: number
  revision?: number
  instance?: string
  pending?: boolean
  source?: string
}

/** Existing neutral line for a built-in provider that is not in the current promotion. */
export const NEUTRAL_PROVIDER_COPY = 'OpenAI 兼容网关。使用已保存的接口地址和密钥。'

/** Register hosts this package already trusts. Not the current promotion list. */
export const TRUSTED_REGISTER_HOSTS: Record<string, string> = {
  apimart: 'go.apimart.ai',
  api88: '88api.ai',
  infistar: 'www.infistar.cc',
  cometapi: 'www.cometapi.com',
  novita: 'novita.ai',
  poyo: 'poyo.ai',
}
const TRUSTED_PROMO_IDS = new Set(Object.keys(TRUSTED_REGISTER_HOSTS))
/** Chooser contents before any signed view is accepted. */
const PACKAGED_ACTIVE = new Set(['apimart'])
let current: PromoSnapshot | null = null
let activeLocale: string | null = null
const listeners = new Set<() => void>()

export function readDynamicProviders(): DynamicProviderSpec[] {
  return current?.providers || []
}

export function findDynamicProvider(id?: string | null): DynamicProviderSpec | undefined {
  if (!id || !current?.providers?.length) return undefined
  return current.providers.find(item => item.id === id)
}

export function dynamicProviderVisibleForLocale(id?: string | null, locale?: string | null): boolean {
  const dynamic = findDynamicProvider(id)
  if (!dynamic || dynamic.locales === undefined) return true
  const loc = normalizePromoLocale(locale ?? activeLocale)
  if (!loc) return dynamic.locales.length > 0
  return dynamic.locales.includes(loc)
}

export function localizedDynamicText(
  map?: Record<string, string> | string | null,
  locale?: string | null,
): string {
  if (!map) return ''
  if (typeof map === 'string') return map
  const loc = normalizePromoLocale(locale ?? activeLocale)
  if (loc && map[loc]) return map[loc]
  return map.en || map.zh || Object.values(map)[0] || ''
}

export function isTrustedSponsorId(id?: string | null): id is string {
  return !!id && (TRUSTED_PROMO_IDS.has(id) || Boolean(findDynamicProvider(id)))
}

export function normalizePromoLocale(language?: string | null): string | null {
  if (!language) return null
  const code = language.trim().toLowerCase().split('-')[0].split('_')[0]
  return code || null
}

export function readPromoLocale(): string | null {
  return activeLocale
}

export function setPromoLocale(language?: string | null) {
  const next = normalizePromoLocale(language)
  if (next === activeLocale) return
  activeLocale = next
  listeners.forEach(listener => listener())
}

export function resolvePromoSlice(snap: PromoSnapshot | null, locale?: string | null): LocalePromoSlice | null {
  if (!snap) return null
  const loc = normalizePromoLocale(locale ?? activeLocale)
  if (loc && snap.byLocale?.[loc]) return snap.byLocale[loc]
  return {
    choices: snap.choices,
    defaultChoice: snap.defaultChoice,
    registerUrls: snap.registerUrls,
    ...(snap.firstRunChoices ? { firstRunChoices: snap.firstRunChoices } : {}),
    ...(snap.firstRunDefault ? { firstRunDefault: snap.firstRunDefault } : {}),
  }
}

export function readPromoSnapshot(): PromoSnapshot | null {
  return current
}

export function writePromoSnapshot(next: PromoSnapshot | null) {
  current = next
  listeners.forEach(listener => listener())
}

export function subscribePromoSnapshot(listener: () => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

function hostOf(url: string): string {
  try { return new URL(url).hostname.toLowerCase().replace(/\.$/, '') } catch { return '' }
}

/**
 * New-user promotion only. fault stays listed and keeps its notice.
 * out_of_service, and a trusted id removed from the accepted choices, leave the recommendation.
 * With no snapshot, eligibility does not block measured providers.
 */
function trustedHostFor(id: string): string {
  if (TRUSTED_REGISTER_HOSTS[id]) return TRUSTED_REGISTER_HOSTS[id]
  const dynamic = findDynamicProvider(id)
  return dynamic ? hostOf(dynamic.registerUrl) : ''
}

export function promotionDelisted(id?: string | null): boolean {
  return !!id && current?.statuses?.[id] === 'out_of_service'
}

export function promotionEligible(id: string, locale?: string | null): boolean {
  if (current?.statuses?.[id] === 'out_of_service') return false
  const slice = resolvePromoSlice(current, locale)
  if (!slice) return true
  if (isTrustedSponsorId(id) && !slice.choices.includes(id)) return false
  return true
}

/** Whether this id is in the promotion the user should see right now. */
export function promotionCurrentlyPromoted(id: string, locale?: string | null): boolean {
  if (!isTrustedSponsorId(id)) return false
  if (current?.statuses?.[id] === 'out_of_service') return false
  const slice = resolvePromoSlice(current, locale)
  if (!slice) return PACKAGED_ACTIVE.has(id)
  return slice.choices.includes(id)
}

export function promotionAllowsUpsell(id: string, locale?: string | null): boolean {
  return promotionCurrentlyPromoted(id, locale)
}

export function promotionRecommends(id: string, locale?: string | null): boolean {
  if (!promotionCurrentlyPromoted(id, locale)) return false
  const slice = resolvePromoSlice(current, locale)
  if (!slice) return id === 'apimart'
  return id === slice.defaultChoice
}

/**
 * Cloud-configured badge override for a promoted provider.
 * - undefined: no override (use default client badge behavior)
 * - null: explicitly hidden via cloud badge=""
 * - non-empty string: localized badge text from cloud config
 */
export function promotionBadge(id: string, locale?: string | null): string | null | undefined {
  if (!promotionCurrentlyPromoted(id, locale)) return undefined
  const raw = current?.badges?.[id]
  if (raw === undefined) return undefined
  if (raw === '') return null
  const text = localizedDynamicText(raw, locale)
  return text || undefined
}

/**
 * Link for a promotion click. The id must be promoted right now, and the URL
 * must use that id's trusted host. An accepted signed view does not fall back
 * to a packaged URL. The packaged URL is used only with no view, or a bundled view.
 */
export function promotionRegisterUrl(id: string, packaged = '', locale?: string | null): string | null {
  if (!promotionCurrentlyPromoted(id, locale)) return null
  const trustedHost = trustedHostFor(id)
  if (!trustedHost) return null
  const slice = resolvePromoSlice(current, locale)
  const remote = slice?.registerUrls?.[id]
  if (typeof remote === 'string' && remote) {
    return hostOf(remote) === trustedHost ? remote : null
  }
  const dynamic = findDynamicProvider(id)
  if (dynamic && hostOf(dynamic.registerUrl) === trustedHost) return dynamic.registerUrl
  if (current && current.source !== 'bundled') return null
  if (!packaged || hostOf(packaged) !== trustedHost) return null
  return packaged
}

/** Remote default when an accepted remote view explicitly sets one. Packaged defaults follow ranked order. */
export function promotionSetupChoice(candidates: readonly string[], locale?: string | null): string | null {
  const listed = candidates.filter(id =>
    !!id
    && id !== 'other'
    && current?.statuses?.[id] !== 'out_of_service'
    && promotionEligible(id, locale)
  )
  const slice = resolvePromoSlice(current, locale)
  const preferred = current && current.source !== 'bundled' ? (slice?.defaultChoice ?? null) : null
  if (preferred && listed.includes(preferred)) return preferred
  return listed[0] || null
}

/** Remote order among promoted sponsors when a view is accepted. Null keeps quality-first ordering. */
export function promotionRank(id: string, locale?: string | null): number | null {
  if (!current) return null
  if (current.statuses[id] === 'out_of_service') return 1000
  const slice = resolvePromoSlice(current, locale)
  if (!slice) return null
  const index = slice.choices.indexOf(id)
  return index === -1 ? null : index
}
