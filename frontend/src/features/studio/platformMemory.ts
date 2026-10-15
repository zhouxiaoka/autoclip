/** Last chosen publish targets. Stored only on this computer; nothing here is sent as text. */

const KEY = 'autoclip.platforms.v1'
export const PLATFORM_IDS = ['douyin', 'tiktok', 'instagram_reels', 'youtube_shorts', 'youtube_long', 'bilibili', 'xiaohongshu'] as const
export type PlatformSource = 'remembered' | 'accounts' | 'locale' | 'user'

type StorageLike = Pick<Storage, 'getItem' | 'setItem'>

function memory(): StorageLike {
  const data = new Map<string, string>()
  return { getItem: key => data.get(key) ?? null, setItem: (key, value) => { data.set(key, value) } }
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

/** First visit: Chinese UI suggests 小红书 and 抖音. Other locales suggest TikTok. */
export function platformsForLocale(locale: string): string[] {
  return locale.toLowerCase().startsWith('zh') ? ['xiaohongshu', 'douyin'] : ['tiktok']
}

export function resolvePlatforms(enabled: boolean, locale: string, remembered: string[] | null = readRememberedPlatforms()): { platforms: string[]; source: PlatformSource } {
  if (!enabled) return { platforms: ['douyin'], source: 'user' }
  if (remembered?.length) return { platforms: knownPlatforms(remembered), source: 'remembered' }
  return { platforms: platformsForLocale(locale), source: 'locale' }
}

export function samePlatforms(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((id, index) => id === right[index])
}
