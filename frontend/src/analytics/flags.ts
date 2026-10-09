/**
 * Typed feature flags. Remote values are read only while analytics is on.
 * Analytics off, offline-without-consent, and a missing key all resolve to the
 * safe off value in flags.defaults.json (plus an explicit local override).
 *
 * Priority: local override → autoclip_safe_mode → PostHog (analytics on) →
 * dev VITE_FLAGS → 7-day cache (analytics on) → build default.
 */
import { useSyncExternalStore } from 'react'
import defaultsJson from './flags.defaults.json'
import { isAnalyticsEnabled, onAnalyticsPreferenceChange, readLoadedFlag, subscribeRemoteFlags } from './posthog'

export const FLAG_NAMES = [
  'autoclip_safe_mode',
  'remember_platforms',
  'one_click_paste_start',
  'link_import_without_whisper',
  'notify_on_done',
  'publish_pack_v2',
  'render_top_first',
  'clip_reasons',
  'hide_legacy_entrypoints',
  'import_drop_zone',
  'track_overrides',
] as const

export type FlagName = (typeof FLAG_NAMES)[number]
export type FlagValue = boolean | string

type FlagSpec = { kind: 'boolean' } | { kind: 'variant'; variants: readonly string[]; treatment: string }

export const FLAG_SPEC: Record<FlagName, FlagSpec> = {
  autoclip_safe_mode: { kind: 'boolean' },
  remember_platforms: { kind: 'boolean' },
  one_click_paste_start: { kind: 'variant', variants: ['button', 'autostart'], treatment: 'autostart' },
  link_import_without_whisper: { kind: 'boolean' },
  notify_on_done: { kind: 'boolean' },
  publish_pack_v2: { kind: 'variant', variants: ['separate', 'combined'], treatment: 'combined' },
  render_top_first: { kind: 'variant', variants: ['limit10', 'top3'], treatment: 'top3' },
  clip_reasons: { kind: 'boolean' },
  hide_legacy_entrypoints: { kind: 'boolean' },
  import_drop_zone: { kind: 'boolean' },
  track_overrides: { kind: 'boolean' },
}

export const FLAG_DEFAULTS = defaultsJson as { [K in FlagName]: FlagValue }

const OVERRIDE_KEY = 'autoclip.flags.overrides.v1'
const CACHE_KEY = 'autoclip.flags.cache.v1'
const CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000

type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

function memoryStorage(): StorageLike {
  const data = new Map<string, string>()
  return { getItem: key => data.get(key) ?? null, setItem: (key, value) => { data.set(key, value) }, removeItem: key => { data.delete(key) } }
}

function browserStorage(): StorageLike {
  try {
    if (typeof localStorage !== 'undefined') return localStorage
  } catch { /* private mode */ }
  return memoryStorage()
}

let storage: StorageLike = browserStorage()
let clock: () => number = () => Date.now()
const listeners = new Set<() => void>()

function notify() {
  for (const listener of listeners) {
    try { listener() } catch { /* one subscriber cannot block the rest */ }
  }
}

export function subscribeFlags(listener: () => void): () => void {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

/** Tests inject storage and time. Production uses localStorage and Date.now. */
export function bindFlagStorage(next: StorageLike) {
  storage = next
  notify()
}

export function bindFlagClock(next: () => number) {
  clock = next
}

export function isFlagName(value: string): value is FlagName {
  return (FLAG_NAMES as readonly string[]).includes(value)
}

export function normalizeFlag(name: FlagName, raw: unknown): FlagValue | undefined {
  const spec = FLAG_SPEC[name]
  if (spec.kind === 'boolean') {
    if (raw === true || raw === 'true' || raw === 'on' || raw === 1 || raw === '1') return true
    if (raw === false || raw === 'false' || raw === 'off' || raw === 0 || raw === '0') return false
    return undefined
  }
  if (typeof raw === 'string' && spec.variants.includes(raw)) return raw
  return undefined
}

function readJson(key: string): Record<string, unknown> | null {
  try {
    const raw = JSON.parse(storage.getItem(key) || 'null') as unknown
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
    return raw as Record<string, unknown>
  } catch {
    return null
  }
}

function readOverride(name: FlagName): FlagValue | undefined {
  const raw = readJson(OVERRIDE_KEY)
  if (!raw || !(name in raw)) return undefined
  return normalizeFlag(name, raw[name])
}

function viteValue(name: FlagName): FlagValue | undefined {
  if (!import.meta.env.DEV) return undefined
  const raw = import.meta.env.VITE_FLAGS
  if (typeof raw !== 'string' || !raw.trim()) return undefined
  for (const part of raw.split(',')) {
    const eq = part.indexOf('=')
    if (eq <= 0) continue
    const key = part.slice(0, eq).trim()
    if (key !== name) continue
    return normalizeFlag(name, part.slice(eq + 1).trim())
  }
  return undefined
}

function readCache(name: FlagName): FlagValue | undefined {
  const raw = readJson(CACHE_KEY)
  const savedAt = raw?.savedAt
  const values = raw?.values
  if (typeof savedAt !== 'number' || !values || typeof values !== 'object' || Array.isArray(values)) return undefined
  if (clock() - savedAt > CACHE_TTL_MS || savedAt > clock()) return undefined
  return normalizeFlag(name, (values as Record<string, unknown>)[name])
}

function rememberCache(name: FlagName, value: FlagValue) {
  if (!isAnalyticsEnabled()) return
  const raw = readJson(CACHE_KEY)
  const savedAt = raw?.savedAt
  const previous = raw?.values
  const fresh = typeof savedAt === 'number' && clock() - savedAt <= CACHE_TTL_MS && previous && typeof previous === 'object' && !Array.isArray(previous)
    ? { ...(previous as Record<string, unknown>) }
    : {}
  fresh[name] = value
  try { storage.setItem(CACHE_KEY, JSON.stringify({ savedAt: clock(), values: fresh })) } catch { /* cache is optional */ }
}

function remoteValue(name: FlagName): FlagValue | undefined {
  if (!isAnalyticsEnabled()) return undefined
  const value = normalizeFlag(name, readLoadedFlag(name))
  if (value === undefined) return undefined
  rememberCache(name, value)
  return value
}

export type FlagOrigin = 'local' | 'safe_mode' | 'remote' | 'vite' | 'cache' | 'default'

/** Where the current value came from. Later PRs emit experiment events only after a real assignment. */
export function flagOrigin(name: FlagName): FlagOrigin {
  if (readOverride(name) !== undefined) return 'local'
  if (name !== 'autoclip_safe_mode' && flagValue('autoclip_safe_mode') === true) return 'safe_mode'
  if (remoteValue(name) !== undefined) return 'remote'
  if (viteValue(name) !== undefined) return 'vite'
  if (isAnalyticsEnabled() && readCache(name) !== undefined) return 'cache'
  return 'default'
}

export function flagAssigned(name: FlagName): boolean {
  const origin = flagOrigin(name)
  return origin === 'local' || origin === 'remote' || origin === 'vite' || origin === 'cache'
}

export function flagValue(name: FlagName): FlagValue {
  const local = readOverride(name)
  if (local !== undefined) return local
  if (name !== 'autoclip_safe_mode' && flagValue('autoclip_safe_mode') === true) return FLAG_DEFAULTS[name]
  const remote = remoteValue(name)
  if (remote !== undefined) return remote
  const vite = viteValue(name)
  if (vite !== undefined) return vite
  if (isAnalyticsEnabled()) {
    const cached = readCache(name)
    if (cached !== undefined) return cached
  }
  return FLAG_DEFAULTS[name]
}

/** True only for the non-default treatment. Safe off (false / control variant) is false. */
export function flagEnabled(name: FlagName): boolean {
  const value = flagValue(name)
  const spec = FLAG_SPEC[name]
  return spec.kind === 'boolean' ? value === true : value === spec.treatment
}

export function flagOverride(name: FlagName): FlagValue | null {
  return readOverride(name) ?? null
}

export function setFlagOverride(name: FlagName, value: FlagValue | null) {
  const current = readJson(OVERRIDE_KEY) || {}
  if (value === null) delete current[name]
  else {
    const normalized = normalizeFlag(name, value)
    if (normalized === undefined) return
    current[name] = normalized
  }
  const next: Record<string, FlagValue> = {}
  for (const key of FLAG_NAMES) {
    const normalized = normalizeFlag(key, current[key])
    if (normalized !== undefined && key in current) next[key] = normalized
  }
  try {
    if (Object.keys(next).length) storage.setItem(OVERRIDE_KEY, JSON.stringify(next))
    else storage.removeItem(OVERRIDE_KEY)
  } catch { /* override still applies in memory for this call; persistence is best effort */ }
  notify()
}

/** Snapshot sent with an import so the backend can reproduce the same decisions. */
export function featureSnapshot(): Record<FlagName, FlagValue> {
  const out = {} as Record<FlagName, FlagValue>
  for (const name of FLAG_NAMES) out[name] = flagValue(name)
  return out
}

export function useFlag(name: FlagName): FlagValue {
  return useSyncExternalStore(subscribeFlags, () => flagValue(name), () => FLAG_DEFAULTS[name])
}

onAnalyticsPreferenceChange(notify)
subscribeRemoteFlags(notify)
