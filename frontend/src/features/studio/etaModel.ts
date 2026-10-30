/** R1 ETA: local history + F1 provider_quality fallback. Pure functions; storage is injectable. */

import qualityRaw from '@provider-quality'

export const ETA_HISTORY_KEY = 'autoclip.eta.history.v1'
export const ETA_INITIAL_KEY = 'autoclip.eta.initial.v1'
const HISTORY_KEEP = 20

export type EtaSample = { provider: string; source_min: number; elapsed_sec: number }

type StorageLike = {
  getItem: (key: string) => string | null
  setItem: (key: string, value: string) => void
}

function memoryStorage(): StorageLike {
  const map = new Map<string, string>()
  return {
    getItem: key => map.get(key) ?? null,
    setItem: (key, value) => { map.set(key, value) },
  }
}

function defaultStorage(): StorageLike {
  try {
    if (typeof localStorage !== 'undefined') return localStorage
  } catch { /* private mode */ }
  return memoryStorage()
}

function median(values: number[]): number | null {
  if (!values.length) return null
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid]! : (sorted[mid - 1]! + sorted[mid]!) / 2
}

/** Builtin wall seconds per minute of source from F1 provider_quality.json. */
export function builtinSecPerSourceMin(provider: string | null | undefined): number | null {
  if (!provider) return null
  const root = qualityRaw as { providers?: Record<string, { sec_per_source_min?: unknown; success_p50_minutes?: unknown }> }
  const row = root.providers?.[provider]
  if (!row || typeof row !== 'object') return null
  const direct = row.sec_per_source_min
  if (typeof direct === 'number' && Number.isFinite(direct) && direct > 0) return direct
  // Calibrated fallback: p50 wall minutes on a ~60 min reference source ≈ sec per source minute.
  const p50 = row.success_p50_minutes
  if (typeof p50 === 'number' && Number.isFinite(p50) && p50 > 0) return p50
  return null
}

export function readHistory(storage: StorageLike = defaultStorage()): EtaSample[] {
  try {
    const raw = JSON.parse(storage.getItem(ETA_HISTORY_KEY) || '[]') as unknown
    if (!Array.isArray(raw)) return []
    return raw.filter((item): item is EtaSample => (
      !!item && typeof item === 'object'
      && typeof (item as EtaSample).provider === 'string'
      && typeof (item as EtaSample).source_min === 'number'
      && typeof (item as EtaSample).elapsed_sec === 'number'
      && (item as EtaSample).source_min > 0
      && (item as EtaSample).elapsed_sec > 0
    )).slice(-HISTORY_KEEP)
  } catch {
    return []
  }
}

export function recordSuccess(sample: EtaSample, storage: StorageLike = defaultStorage()): void {
  if (!sample.provider || !(sample.source_min > 0) || !(sample.elapsed_sec > 0)) return
  const next = [...readHistory(storage), sample].slice(-HISTORY_KEEP)
  try { storage.setItem(ETA_HISTORY_KEY, JSON.stringify(next)) } catch { /* quota */ }
}

/** Median sec/source_min from the last 5 same-provider successes. */
export function medianSecPerSourceMin(provider: string, history: EtaSample[] = readHistory()): number | null {
  if (!provider) return null
  const rates = history
    .filter(item => item.provider === provider && item.source_min > 0)
    .slice(-5)
    .map(item => item.elapsed_sec / item.source_min)
    .filter(rate => Number.isFinite(rate) && rate > 0)
  return median(rates)
}

export function rememberInitialEta(runKey: string, initialMin: number, storage: StorageLike = defaultStorage()): void {
  if (!runKey || !(initialMin > 0)) return
  let all: Record<string, number> = {}
  try { all = JSON.parse(storage.getItem(ETA_INITIAL_KEY) || '{}') as Record<string, number> } catch { all = {} }
  if (!all || typeof all !== 'object') all = {}
  all[runKey] = initialMin
  const keys = Object.keys(all)
  if (keys.length > 40) {
    for (const key of keys.slice(0, keys.length - 40)) delete all[key]
  }
  try { storage.setItem(ETA_INITIAL_KEY, JSON.stringify(all)) } catch { /* quota */ }
}

export function readInitialEta(runKey: string, storage: StorageLike = defaultStorage()): number | null {
  if (!runKey) return null
  try {
    const all = JSON.parse(storage.getItem(ETA_INITIAL_KEY) || '{}') as Record<string, unknown>
    const value = all?.[runKey]
    return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : null
  } catch {
    return null
  }
}

export type EtaEstimate = {
  /** Whole minutes still expected. Null when unknown or overrun copy should replace the number. */
  etaMin: number | null
  overrun: boolean
  /** Total ETA at first estimate (minutes). */
  initialMin: number | null
  /** Actual elapsed / initial ETA. */
  errorRatio: number | null
}

/**
 * estimate(provider, sourceMin, concurrency): remaining minutes from local median
 * or F1 sec_per_source_min × source_min ÷ concurrency. Overrun when elapsed > 2× initial.
 */
export function estimate(
  provider: string | null | undefined,
  sourceMin: number,
  concurrency = 1,
  elapsedSec = 0,
  options?: { history?: EtaSample[]; builtin?: number | null; runKey?: string; storage?: StorageLike },
): EtaEstimate {
  const empty: EtaEstimate = { etaMin: null, overrun: false, initialMin: null, errorRatio: null }
  if (!(sourceMin > 0) || !provider) return empty
  const workers = concurrency > 0 ? concurrency : 1
  const storage = options?.storage ?? defaultStorage()
  const history = options?.history ?? readHistory(storage)
  const rate = medianSecPerSourceMin(provider, history)
    ?? (options?.builtin !== undefined ? options.builtin : builtinSecPerSourceMin(provider))
  if (!(typeof rate === 'number') || !(rate > 0)) return empty
  const totalSec = (rate * sourceMin) / workers
  if (!(totalSec > 0)) return empty
  const initialMin = Math.max(1, Math.round(totalSec / 60))
  if (options?.runKey) {
    const prior = readInitialEta(options.runKey, storage)
    if (prior == null) rememberInitialEta(options.runKey, initialMin, storage)
  }
  const lockedInitial = (options?.runKey ? readInitialEta(options.runKey, storage) : null) ?? initialMin
  const lockedTotalSec = lockedInitial * 60
  const ratio = lockedTotalSec > 0 ? Math.max(0, elapsedSec) / lockedTotalSec : null
  const overrun = ratio != null && ratio > 2
  if (overrun) {
    return { etaMin: null, overrun: true, initialMin: lockedInitial, errorRatio: ratio }
  }
  const remainingSec = Math.max(0, lockedTotalSec - Math.max(0, elapsedSec))
  const etaMin = Math.max(1, Math.ceil(remainingSec / 60))
  return { etaMin, overrun: false, initialMin: lockedInitial, errorRatio: ratio }
}
