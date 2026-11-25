/** Paste-to-start decisions. The URL itself is never returned to telemetry. */

export const UNDO_MS = 3000
export type StartTrigger = 'paste' | 'drop' | 'button'

const VIDEO = /\.(mp4|mov|mkv|webm|avi|m4v|flv|ts|mts|m2ts|mpg|mpeg|wmv)$/i

export function importUrlKind(text: string): 'youtube' | 'bilibili' | null {
  const value = text.trim()
  if (!value || /\s/.test(value)) return null
  try {
    const url = new URL(value)
    if (url.protocol !== 'https:' || url.username || url.password) return null
    const host = url.hostname.toLowerCase()
    if (host === 'youtu.be' || host === 'youtube.com' || host.endsWith('.youtube.com')) return 'youtube'
    if (host === 'b23.tv' || host === 'bilibili.com' || host.endsWith('.bilibili.com')) return 'bilibili'
  } catch { /* not a link */ }
  return null
}

const URL_TOKEN = /https?:\/\/[^\s"'<>`]+/gi
const BARE_IMPORT_URL = /(?:^|[\s"'<>`])((?:(?:www|m|music)\.)?(?:youtube\.com|youtu\.be|bilibili\.com|b23\.tv)\/[^\s"'<>`]+)/gi
const TRAILING_PUNCT = /[.,;:!?)\]】》」"'、，。！？]+$/

/** Extract a single supported YouTube/Bilibili URL from plain links, bare domain links, or share text (e.g. Bilibili `【标题】 https://b23.tv/...`). */
export function extractImportUrl(text: string): string | null {
  const raw = (text || '').trim()
  if (!raw) return null
  const matches = raw.match(URL_TOKEN)
  if (matches) {
    if (matches.length !== 1) return null
    const candidate = matches[0].replace(TRAILING_PUNCT, '')
    const upgraded = candidate.replace(/^http:\/\//i, 'https://')
    return importUrlKind(upgraded) ? upgraded : null
  }
  const bare = [...raw.matchAll(BARE_IMPORT_URL)].map(m => m[1])
  if (bare.length !== 1) return null
  const candidate = `https://${bare[0].replace(TRAILING_PUNCT, '')}`
  return importUrlKind(candidate) ? candidate : null
}

export function isVideoFile(file: { name?: string; type?: string } | null | undefined): boolean {
  if (!file) return false
  return /^video\//.test(file.type || '') || VIDEO.test(file.name || '')
}

export function shouldAutoStart(flag: string, trigger: StartTrigger): boolean {
  return flag === 'autostart' && (trigger === 'paste' || trigger === 'drop')
}

/** F4: paste/drop autostart countdown starts only after the URL preview card is ready. */
export function shouldArmAutostart(flag: string, trigger: StartTrigger, previewReady: boolean): boolean {
  if (trigger === 'drop') return shouldAutoStart(flag, trigger)
  return shouldAutoStart(flag, trigger) && previewReady
}

export function undoDeadline(now: number): number {
  return now + UNDO_MS
}

export function undoOpen(deadline: number, now: number): boolean {
  return now < deadline
}

let backgroundClaimed = false

export function claimBackgroundWhisperInstall(): boolean {
  if (backgroundClaimed) return false
  backgroundClaimed = true
  return true
}

export function resetBackgroundWhisperInstall() {
  backgroundClaimed = false
}

export function shouldBackgroundInstallWhisper(enabled: boolean, code: string | undefined): boolean {
  return enabled && code === 'whisper_not_installed'
}
