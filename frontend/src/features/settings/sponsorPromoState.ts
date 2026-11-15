/**
 * Accepted promotion snapshot. No provider imports, so pickers and failure actions can read it
 * without a cycle. Empty until a watcher publishes a validated view.
 */
export interface PromoSnapshot {
  choices: string[]
  defaultChoice: string
  statuses: Record<string, string>
  registerUrls: Record<string, string>
  notices: Record<string, Record<string, string>>
  sequence?: number
  revision?: number
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
}
const TRUSTED_PROMO_IDS = new Set(Object.keys(TRUSTED_REGISTER_HOSTS))
/** Chooser contents before any signed view is accepted. */
const PACKAGED_ACTIVE = new Set(['apimart'])
let current: PromoSnapshot | null = null
const listeners = new Set<() => void>()

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
export function promotionEligible(id: string): boolean {
  if (current?.statuses?.[id] === 'out_of_service') return false
  if (!current) return true
  if (TRUSTED_PROMO_IDS.has(id) && !current.choices.includes(id)) return false
  return true
}

/** Whether this id is in the promotion the user should see right now. */
export function promotionCurrentlyPromoted(id: string): boolean {
  if (!TRUSTED_PROMO_IDS.has(id)) return false
  if (current?.statuses?.[id] === 'out_of_service') return false
  if (!current) return PACKAGED_ACTIVE.has(id)
  return current.choices.includes(id)
}

export function promotionAllowsUpsell(id: string): boolean {
  return promotionCurrentlyPromoted(id)
}

export function promotionRecommends(id: string): boolean {
  if (!promotionCurrentlyPromoted(id)) return false
  if (!current) return id === 'apimart'
  return id === current.defaultChoice
}

/**
 * Link for a promotion click. The id must be promoted right now, and the URL
 * must use that id's trusted host. An accepted signed view does not fall back
 * to a packaged URL. The packaged URL is used only with no view, or a bundled view.
 */
export function promotionRegisterUrl(id: string, packaged = ''): string | null {
  if (!promotionCurrentlyPromoted(id)) return null
  const remote = current?.registerUrls?.[id]
  if (typeof remote === 'string' && remote) {
    return hostOf(remote) === TRUSTED_REGISTER_HOSTS[id] ? remote : null
  }
  if (current && current.source !== 'bundled') return null
  if (!packaged || hostOf(packaged) !== TRUSTED_REGISTER_HOSTS[id]) return null
  return packaged
}

/** Remote default when it is still selectable. Null when nothing legal remains. */
export function promotionSetupChoice(candidates: readonly string[]): string | null {
  const listed = candidates.filter(id =>
    !!id
    && id !== 'other'
    && current?.statuses?.[id] !== 'out_of_service'
    && promotionEligible(id)
  )
  const preferred = current?.defaultChoice
  if (preferred && listed.includes(preferred)) return preferred
  return listed[0] || null
}

/** Remote order when a view is accepted. Null keeps the packaged sort. */
export function promotionRank(id: string): number | null {
  if (!current) return null
  if (current.statuses[id] === 'out_of_service') return 1000
  const index = current.choices.indexOf(id)
  return index === -1 ? 100 : index
}
