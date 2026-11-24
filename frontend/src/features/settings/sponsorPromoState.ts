/**
 * Accepted promotion snapshot. No provider imports, so pickers and failure actions can read it
 * without a cycle. Empty until a watcher publishes a validated view.
 */
export interface LocalePromoSlice {
  choices: string[]
  defaultChoice: string
  registerUrls: Record<string, string>
}

export interface PromoSnapshot {
  choices: string[]
  defaultChoice: string
  statuses: Record<string, string>
  registerUrls: Record<string, string>
  notices: Record<string, Record<string, string>>
  byLocale?: Record<string, LocalePromoSlice>
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

export function isTrustedSponsorId(id?: string | null): id is string {
  return !!id && TRUSTED_PROMO_IDS.has(id)
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
export function promotionEligible(id: string, locale?: string | null): boolean {
  if (current?.statuses?.[id] === 'out_of_service') return false
  const slice = resolvePromoSlice(current, locale)
  if (!slice) return true
  if (TRUSTED_PROMO_IDS.has(id) && !slice.choices.includes(id)) return false
  return true
}

/** Whether this id is in the promotion the user should see right now. */
export function promotionCurrentlyPromoted(id: string, locale?: string | null): boolean {
  if (!TRUSTED_PROMO_IDS.has(id)) return false
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
 * Link for a promotion click. The id must be promoted right now, and the URL
 * must use that id's trusted host. An accepted signed view does not fall back
 * to a packaged URL. The packaged URL is used only with no view, or a bundled view.
 */
export function promotionRegisterUrl(id: string, packaged = '', locale?: string | null): string | null {
  if (!promotionCurrentlyPromoted(id, locale)) return null
  const slice = resolvePromoSlice(current, locale)
  const remote = slice?.registerUrls?.[id]
  if (typeof remote === 'string' && remote) {
    return hostOf(remote) === TRUSTED_REGISTER_HOSTS[id] ? remote : null
  }
  if (current && current.source !== 'bundled') return null
  if (!packaged || hostOf(packaged) !== TRUSTED_REGISTER_HOSTS[id]) return null
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
