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

const PACKAGED_SPONSORS = new Set(['apimart', 'api88'])
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

/**
 * New-user promotion only. fault stays listed and keeps its notice.
 * out_of_service, and a packaged sponsor removed from the accepted choices, leave the recommendation.
 */
export function promotionEligible(id: string): boolean {
  if (!current) return true
  if (current.statuses[id] === 'out_of_service') return false
  if (PACKAGED_SPONSORS.has(id) && !current.choices.includes(id)) return false
  return true
}

export function promotionAllowsUpsell(id: string): boolean {
  if (!promotionEligible(id)) return false
  if (!current) return PACKAGED_SPONSORS.has(id)
  return current.choices.includes(id) && PACKAGED_SPONSORS.has(id)
}

export function promotionRecommends(id: string): boolean {
  if (current?.statuses?.[id] === 'out_of_service') return false
  if (!current) return id === 'apimart'
  return id === current.defaultChoice
}

export function promotionRegisterUrl(id: string, packaged = ''): string | null {
  if (!promotionAllowsUpsell(id)) return null
  return current?.registerUrls?.[id] || packaged || null
}

/** Remote order when a view is accepted. Null keeps the packaged sort. */
export function promotionRank(id: string): number | null {
  if (!current) return null
  if (current.statuses[id] === 'out_of_service') return 1000
  const index = current.choices.indexOf(id)
  return index === -1 ? 100 : index
}
