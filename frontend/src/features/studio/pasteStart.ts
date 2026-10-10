/** Paste-to-start decisions. The URL itself is never returned to telemetry. */

export const UNDO_MS = 3000
export type StartTrigger = 'paste' | 'drop' | 'button'

const VIDEO = /\.(mp4|mov|mkv|webm|avi)$/i

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

export function isVideoFile(file: { name?: string; type?: string } | null | undefined): boolean {
  if (!file) return false
  return /^video\//.test(file.type || '') || VIDEO.test(file.name || '')
}

export function shouldAutoStart(flag: string, trigger: StartTrigger): boolean {
  return flag === 'autostart' && (trigger === 'paste' || trigger === 'drop')
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
