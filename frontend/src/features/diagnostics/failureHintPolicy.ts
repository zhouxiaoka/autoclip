/** First-failure hint. This preference is not diagnostics consent and never changes it. */

export const FAILURE_HINT_KEY = 'autoclip.diagnostics.failure_hint.v1'
export const FAILURE_HINT_MS = 7000
/** Hover or focus can pause the short timer, but the hint still leaves. */
export const FAILURE_HINT_MAX_MS = 20000

export type TaskOrigin = 'file' | 'link' | 'unknown'
export type HintKind = 'on' | 'off'

export const HINT_COPY: Record<HintKind, string> = {
  on: '我们会收集本次错误信息，帮助改善体验，可在设置中关闭。',
  off: '这次不会自动发送内容。可以在设置中打开。',
}

type ConsentLike = { diagnostics?: boolean; media?: boolean; unreadable?: boolean }
type StorageLike = Pick<Storage, 'getItem' | 'setItem'>

function taggedOrigin(value: object | null | undefined): 'file' | 'link' | undefined {
  if (!value || !('input_origin' in value)) return undefined
  const origin = (value as { input_origin?: unknown }).input_origin
  return origin === 'file' || origin === 'link' ? origin : undefined
}

const FAILED = new Set(['failed', 'error'])

/** A project that is already failed on first sight is history. Only a live flip arms the hint. */
export function nextLiveFailure<T extends { id: string; status?: string | null }>(
  previous: Record<string, string>,
  projects: T[],
): { previous: Record<string, string>; failed: T | null } {
  const next = { ...previous }
  let failed: T | null = null
  for (const project of projects) {
    const status = typeof project.status === 'string' ? project.status : ''
    const before = previous[project.id]
    if (before && !FAILED.has(before) && FAILED.has(status)) failed = project
    if (status) next[project.id] = status
  }
  return { previous: next, failed }
}

export function taskOrigin(project: {
  source_url?: string | null
  source_file?: string | null
  video_path?: string | null
  settings?: object | null
  processing_config?: object | null
}): TaskOrigin {
  const url = typeof project.source_url === 'string' ? project.source_url.trim() : ''
  const http = /^https?:\/\//i.test(url)
  const file = [project.source_file, project.video_path].some(value => typeof value === 'string' && value.trim().length > 0)
  const tagged = [taggedOrigin(project.settings), taggedOrigin(project.processing_config)].find(value => value === 'file' || value === 'link')
  if (http && (file || tagged === 'file')) return 'unknown'
  if (tagged === 'link' || http) return 'link'
  if (tagged === 'file' || file) return 'file'
  return 'unknown'
}

/** The short hint never mentions video. An explicit off choice must not claim that anything is collected. */
export function hintKind(_origin: TaskOrigin, consent: ConsentLike): HintKind {
  if (consent.unreadable || consent.diagnostics !== true) return 'off'
  return 'on'
}

export function hintSeen(storage: Pick<Storage, 'getItem'>): boolean {
  try {
    return storage.getItem(FAILURE_HINT_KEY) === '1'
  } catch {
    return true
  }
}

export function rememberHint(storage: Pick<Storage, 'setItem'>): void {
  storage.setItem(FAILURE_HINT_KEY, '1')
}

/** One show per browser profile. A later page load reads the same key and stays quiet. */
export function createHintGate(storage: StorageLike) {
  let claimed = false
  return {
    claim(): boolean {
      if (claimed || hintSeen(storage)) return false
      claimed = true
      try {
        rememberHint(storage)
      } catch {
        /* This session still shows once. A storage failure must not rewrite consent. */
      }
      return true
    },
  }
}

const session = createHintGate(typeof localStorage === 'undefined'
  ? { getItem: () => null, setItem: () => undefined }
  : localStorage)

export function claimFailureHint(storage: StorageLike = localStorage): boolean {
  if (storage !== localStorage) return createHintGate(storage).claim()
  return session.claim()
}

type Schedule = (fn: () => void, ms: number) => ReturnType<typeof setTimeout>
type Cancel = (id: ReturnType<typeof setTimeout>) => void

export function createHintTimer(duration: number, onDone: () => void, schedule: Schedule = setTimeout, cancel: Cancel = clearTimeout) {
  let remaining = duration
  let startedAt = 0
  let timer: ReturnType<typeof setTimeout> | null = null
  let running = false
  let paused = false
  let finished = false
  const clear = () => {
    if (timer !== null) cancel(timer)
    timer = null
    running = false
  }
  return {
    get remaining() { return remaining },
    get paused() { return paused },
    start(now = Date.now()) {
      if (finished || paused || running) return
      startedAt = now
      running = true
      timer = schedule(() => {
        running = false
        timer = null
        finished = true
        onDone()
      }, remaining)
    },
    pause(now = Date.now()) {
      if (finished || paused || !running) return
      paused = true
      remaining = Math.max(0, remaining - (now - startedAt))
      clear()
    },
    resume(now = Date.now()) {
      if (finished || !paused) return
      paused = false
      this.start(now)
    },
    stop() {
      finished = true
      clear()
    },
  }
}
