/**
 * Measured success / latency tiers from backend/presets/provider_quality.json.
 * No network request. Providers missing from the file have no tier.
 */
import raw from '@provider-quality'

export type SuccessTier = 'high' | 'mid' | 'low'
export type LatencyTier = 'under_5m' | 'mid_5_20m' | 'over_20m'
export type CatalogGroup = 'recommended' | 'popular' | 'local' | 'more'
export type PickerGroup = 'sponsor' | 'cloud' | 'compatible' | 'local'

export type ProviderQuality = {
  success_rate: number
  success_p50_minutes: number
  success_tier: SuccessTier
  latency_tier: LatencyTier
  caveat_key?: string
}

type Thresholds = {
  success_high_min: number
  success_mid_min: number
  latency_under_5m_exclusive_max_minutes: number
  latency_mid_inclusive_max_minutes: number
}

const DEFAULT_THRESHOLDS: Thresholds = {
  success_high_min: 0.8,
  success_mid_min: 0.6,
  latency_under_5m_exclusive_max_minutes: 5,
  latency_mid_inclusive_max_minutes: 20,
}

const TIER_RANK: Record<SuccessTier, number> = { high: 3, mid: 2, low: 1 }

function numberOf(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

export function successTierOf(rate: number, thresholds: Thresholds = DEFAULT_THRESHOLDS): SuccessTier | undefined {
  if (!Number.isFinite(rate) || rate < 0 || rate > 1) return undefined
  if (rate >= thresholds.success_high_min) return 'high'
  if (rate >= thresholds.success_mid_min) return 'mid'
  return 'low'
}

export function latencyTierOf(minutes: number, thresholds: Thresholds = DEFAULT_THRESHOLDS): LatencyTier | undefined {
  if (!Number.isFinite(minutes) || minutes < 0) return undefined
  if (minutes < thresholds.latency_under_5m_exclusive_max_minutes) return 'under_5m'
  if (minutes <= thresholds.latency_mid_inclusive_max_minutes) return 'mid_5_20m'
  return 'over_20m'
}

function parseQuality(document: unknown): { thresholds: Thresholds; providers: Record<string, ProviderQuality> } {
  const data = document && typeof document === 'object' ? document as Record<string, unknown> : {}
  const rawThresholds = data.thresholds && typeof data.thresholds === 'object' ? data.thresholds as Record<string, unknown> : {}
  const thresholds: Thresholds = {
    success_high_min: numberOf(rawThresholds.success_high_min) ?? DEFAULT_THRESHOLDS.success_high_min,
    success_mid_min: numberOf(rawThresholds.success_mid_min) ?? DEFAULT_THRESHOLDS.success_mid_min,
    latency_under_5m_exclusive_max_minutes: numberOf(rawThresholds.latency_under_5m_exclusive_max_minutes) ?? DEFAULT_THRESHOLDS.latency_under_5m_exclusive_max_minutes,
    latency_mid_inclusive_max_minutes: numberOf(rawThresholds.latency_mid_inclusive_max_minutes) ?? DEFAULT_THRESHOLDS.latency_mid_inclusive_max_minutes,
  }
  const providers: Record<string, ProviderQuality> = {}
  const rows = data.providers && typeof data.providers === 'object' ? data.providers as Record<string, unknown> : {}
  for (const [id, value] of Object.entries(rows)) {
    if (!value || typeof value !== 'object') continue
    const row = value as Record<string, unknown>
    const success_rate = numberOf(row.success_rate)
    const success_p50_minutes = numberOf(row.success_p50_minutes)
    if (success_rate === undefined || success_p50_minutes === undefined) continue
    const success_tier = successTierOf(success_rate, thresholds)
    const latency_tier = latencyTierOf(success_p50_minutes, thresholds)
    if (!success_tier || !latency_tier) continue
    const caveat = typeof row.caveat_key === 'string' ? row.caveat_key.trim() : ''
    providers[id] = {
      success_rate,
      success_p50_minutes,
      success_tier,
      latency_tier,
      ...(caveat ? { caveat_key: caveat } : {}),
    }
  }
  return { thresholds, providers }
}

const table = parseQuality(raw)

export function qualityThresholds(): Thresholds {
  return table.thresholds
}

export function qualityFor(id?: string | null): ProviderQuality | undefined {
  if (!id) return undefined
  return table.providers[id]
}

export function displayCatalogGroup(preset: {
  group: CatalogGroup
  sponsor?: unknown
  success_tier?: SuccessTier
}): CatalogGroup {
  if (preset.success_tier === 'low') {
    if (preset.group === 'local') return 'local'
    if (preset.group === 'more') return 'more'
    return 'popular'
  }
  if (preset.sponsor || preset.group === 'recommended') return 'recommended'
  if ((preset.success_tier === 'high' || preset.success_tier === 'mid') && preset.group === 'popular') return 'recommended'
  return preset.group
}

export function pickerBucket(stored: PickerGroup, tier?: SuccessTier): PickerGroup {
  if (tier === 'low') {
    if (stored === 'local') return 'local'
    if (stored === 'compatible') return 'compatible'
    return 'cloud'
  }
  if (stored === 'sponsor') return 'sponsor'
  if ((tier === 'high' || tier === 'mid') && stored === 'cloud') return 'sponsor'
  return stored
}

export function compareRecommended(
  a: { sponsor?: unknown; success_tier?: SuccessTier; success_rate?: number },
  b: { sponsor?: unknown; success_tier?: SuccessTier; success_rate?: number },
): number {
  const aSponsor = a.sponsor ? 1 : 0
  const bSponsor = b.sponsor ? 1 : 0
  if (aSponsor !== bSponsor) return bSponsor - aSponsor
  if (aSponsor && bSponsor) return 0
  const aRank = a.success_tier ? TIER_RANK[a.success_tier] : 0
  const bRank = b.success_tier ? TIER_RANK[b.success_tier] : 0
  if (aRank !== bRank) return bRank - aRank
  const aRate = a.success_rate ?? -1
  const bRate = b.success_rate ?? -1
  if (aRate !== bRate) return bRate - aRate
  return 0
}

const ZH_OTHER_CANDIDATES = ['deepseek', 'dashscope'] as const

export function pickHigherQuality<T extends string>(ids: readonly T[]): T {
  return [...ids].sort((a, b) => compareRecommended(
    { success_tier: qualityFor(a)?.success_tier, success_rate: qualityFor(a)?.success_rate },
    { success_tier: qualityFor(b)?.success_tier, success_rate: qualityFor(b)?.success_rate },
  ))[0]
}

/** zh compares DeepSeek and DashScope; every other locale stays on DeepSeek. */
export function firstRunOtherDefault(language?: string): 'deepseek' | 'dashscope' {
  if (!(language || '').toLowerCase().startsWith('zh')) return 'deepseek'
  return pickHigherQuality(ZH_OTHER_CANDIDATES)
}
