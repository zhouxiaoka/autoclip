/** Last chosen publish targets. Stored only on this computer; nothing here is sent as text. */

const KEY = 'autoclip.platforms.v1'
/** ISO timestamp of the first successful generation on this device (T1). */
export const FIRST_SUCCESS_KEY = 'autoclip.first_success_at.v1'
/** One-shot stash: reuse source + preselect platforms when starting another project (T1 banner). */
export const REUSE_IMPORT_KEY = 'autoclip.t1.reuse_import.v1'
/** Dismissed the 「再做一个平台」 banner once. */
export const MORE_PLATFORM_BANNER_KEY = 'autoclip.t1.more_platform_banner_seen.v1'

export const PLATFORM_IDS = ['douyin', 'tiktok', 'instagram_reels', 'youtube_shorts', 'youtube_long', 'bilibili', 'xiaohongshu'] as const
export type PlatformSource = 'remembered' | 'accounts' | 'locale' | 'user'

type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

function memory(): StorageLike {
  const data = new Map<string, string>()
  return {
    getItem: key => data.get(key) ?? null,
    setItem: (key, value) => { data.set(key, value) },
    removeItem: key => { data.delete(key) },
  }
}

function browserStorage(): StorageLike {
  try {
    if (typeof localStorage !== 'undefined') return localStorage
  } catch { /* private mode */ }
  return memory()
}

let storage: StorageLike = browserStorage()

export function bindPlatformStorage(next: StorageLike) {
  storage = next
}

export function knownPlatforms(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  const ids = value.filter((item): item is string => typeof item === 'string' && (PLATFORM_IDS as readonly string[]).includes(item))
  return [...new Set(ids)]
}

export function readRememberedPlatforms(): string[] | null {
  try {
    const ids = knownPlatforms(JSON.parse(storage.getItem(KEY) || 'null'))
    return ids.length ? ids : null
  } catch {
    return null
  }
}

export function writeRememberedPlatforms(ids: string[]) {
  const next = knownPlatforms(ids)
  if (!next.length) return
  try { storage.setItem(KEY, JSON.stringify(next)) } catch { /* remembering is optional */ }
}

export function hasSuccessHistory(box: StorageLike = storage): boolean {
  try {
    const value = box.getItem(FIRST_SUCCESS_KEY)
    return typeof value === 'string' && value.length > 0
  } catch {
    return false
  }
}

/** Record the first device success. Returns true when this call wrote the stamp. */
export function markFirstSuccess(at: string = new Date().toISOString(), box: StorageLike = storage): boolean {
  if (hasSuccessHistory(box)) return false
  if (!at) return false
  try {
    box.setItem(FIRST_SUCCESS_KEY, at)
    return true
  } catch {
    return false
  }
}

/**
 * T1: no success history → one platform only (zh → douyin, else → tiktok).
 * After first success → zh keeps 小红书+抖音; other locales keep TikTok.
 */
export function platformsForLocale(locale: string, successHistory: boolean = hasSuccessHistory()): string[] {
  const zh = locale.toLowerCase().startsWith('zh')
  if (!successHistory) return zh ? ['douyin'] : ['tiktok']
  return zh ? ['xiaohongshu', 'douyin'] : ['tiktok']
}

export function resolvePlatforms(
  enabled: boolean,
  locale: string,
  remembered: string[] | null = readRememberedPlatforms(),
  successHistory: boolean = hasSuccessHistory(),
): { platforms: string[]; source: PlatformSource } {
  if (!enabled) return { platforms: ['douyin'], source: 'user' }
  if (remembered?.length) return { platforms: knownPlatforms(remembered), source: 'remembered' }
  return { platforms: platformsForLocale(locale, successHistory), source: 'locale' }
}

export function samePlatforms(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((id, index) => id === right[index])
}

/** Suggest one more platform for the T1 post-success banner. */
export function suggestAnotherPlatform(locale: string, already: string[] = []): string {
  const have = new Set(knownPlatforms(already))
  const zh = locale.toLowerCase().startsWith('zh')
  const order = zh
    ? ['xiaohongshu', 'douyin', 'bilibili', 'youtube_shorts']
    : ['youtube_shorts', 'tiktok', 'instagram_reels', 'youtube_long']
  for (const id of order) {
    if (!have.has(id)) return id
  }
  return zh ? 'xiaohongshu' : 'youtube_shorts'
}

export type ReuseImport = {
  platforms: string[]
  sourceUrl?: string
  /** Opaque source metadata from the finished project (path / kind); not uploaded as analytics. */
  sourceMeta?: {
    source_url?: string
    source_file?: string
    video_path?: string
    project_id?: string
  }
}

export function stashReuseImport(payload: ReuseImport, box: StorageLike = storage): void {
  const platforms = knownPlatforms(payload.platforms)
  if (!platforms.length) return
  try {
    box.setItem(REUSE_IMPORT_KEY, JSON.stringify({
      platforms,
      sourceUrl: typeof payload.sourceUrl === 'string' ? payload.sourceUrl : undefined,
      sourceMeta: payload.sourceMeta && typeof payload.sourceMeta === 'object' ? payload.sourceMeta : undefined,
    }))
  } catch { /* optional */ }
}

/** Read and clear the one-shot reuse stash. */
export function takeReuseImport(box: StorageLike = storage): ReuseImport | null {
  try {
    const raw = box.getItem(REUSE_IMPORT_KEY)
    if (!raw) return null
    box.removeItem(REUSE_IMPORT_KEY)
    const parsed = JSON.parse(raw) as ReuseImport
    const platforms = knownPlatforms(parsed?.platforms)
    if (!platforms.length) return null
    return {
      platforms,
      sourceUrl: typeof parsed.sourceUrl === 'string' ? parsed.sourceUrl : undefined,
      sourceMeta: parsed.sourceMeta && typeof parsed.sourceMeta === 'object' ? parsed.sourceMeta : undefined,
    }
  } catch {
    try { box.removeItem(REUSE_IMPORT_KEY) } catch { /* ignore */ }
    return null
  }
}

export function morePlatformBannerSeen(box: StorageLike = storage): boolean {
  try { return box.getItem(MORE_PLATFORM_BANNER_KEY) === '1' } catch { return false }
}

export function dismissMorePlatformBanner(box: StorageLike = storage): void {
  try { box.setItem(MORE_PLATFORM_BANNER_KEY, '1') } catch { /* ignore */ }
}
