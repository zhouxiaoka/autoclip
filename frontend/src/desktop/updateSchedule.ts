/** 自动检查的节流，以及下载进度、更新说明摘要。不依赖 Tauri。 */

export const UPDATE_CHECK_INTERVAL_MS = 24 * 60 * 60 * 1000
export const LAST_CHECK_KEY = 'autoclip.updater.lastCheckAt'
export const LAST_RESULT_KEY = 'autoclip.updater.lastResult'
export const SNOOZE_KEY = 'autoclip.updater.snoozeVersion'

export type CheckResult = 'current' | 'available'

type Reader = { getItem(key: string): string | null }
type Writer = { setItem(key: string, value: string): void }

export function shouldCheckAutomatically(storage: Reader, now: number, interval = UPDATE_CHECK_INTERVAL_MS): boolean {
  if (storage.getItem(LAST_RESULT_KEY) === 'available') return true
  const last = Number(storage.getItem(LAST_CHECK_KEY) || 0)
  if (!Number.isFinite(last) || last <= 0) return true
  return now - last >= interval
}

export function rememberSuccessfulCheck(storage: Writer, now: number, result: CheckResult): void {
  storage.setItem(LAST_CHECK_KEY, String(now))
  storage.setItem(LAST_RESULT_KEY, result)
}

export type ProgressSnap = { received: number; total: number; percent: number | null }

export function applyDownloadEvent(
  snap: ProgressSnap,
  event: { event: string; data?: { contentLength?: number; chunkLength?: number } },
): ProgressSnap {
  if (event.event === 'Started') {
    const total = event.data?.contentLength ?? 0
    return { received: 0, total, percent: total > 0 ? 0 : null }
  }
  if (event.event === 'Progress') {
    const received = snap.received + (event.data?.chunkLength ?? 0)
    const percent = snap.total > 0 ? Math.min(100, Math.round((received / snap.total) * 100)) : null
    return { received, total: snap.total, percent }
  }
  if (event.event === 'Finished') return { ...snap, percent: 100 }
  return snap
}

/** 更新说明只留一两句可读的正文，给右下角提示用。 */
export function previewNotes(body: string | null | undefined, max = 180): string {
  if (!body) return ''
  const text = body
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('#') && !line.startsWith('|') && line !== '---')
    .map((line) => line.replace(/^[-*]\s+/, '').replace(/`/g, ''))
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim()
  if (text.length <= max) return text
  return `${text.slice(0, max).trimEnd()}…`
}

export function displayError(err: unknown): string {
  const text = err instanceof Error ? err.message : String(err)
  return text.split('{{').join('{').slice(0, 240)
}
