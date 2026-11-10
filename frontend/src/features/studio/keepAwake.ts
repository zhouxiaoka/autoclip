/**
 * System keep-awake while any project is producing.
 * Acquire when a source is active; release 10s after the last one stops.
 * Setting 「制作时阻止电脑休眠」 defaults on (localStorage).
 *
 * The native lock has three states: held, released, unknown. Unknown means the
 * last command failed or a newer command superseded it, so the UI must not say
 * production is still running and must not claim the machine may sleep.
 * The header pill is shown only while a source is active and the lock is confirmed.
 * A failed release retries on a bounded backoff, then again on a later sync
 * after that window. It does not poll.
 */

export const KEEP_AWAKE_SETTING_KEY = 'autoclip.keep_awake.enabled.v1'
export const KEEP_AWAKE_RELEASE_DELAY_MS = 10_000
/** One immediate attempt, then these delays. After the last delay, wait for a later sync. */
export const KEEP_AWAKE_RETRY_BACKOFF_MS = [1_000, 2_000, 4_000, 8_000, 16_000] as const

const RUNNING_GENERATION = new Set(['screening', 'production', 'rendering'])

export type KeepAwakeLockState = 'held' | 'released' | 'unknown'

export type KeepAwakeProjectLike = {
  status?: string
  settings?: { studio_generation_status?: string; [key: string]: unknown }
  processing_config?: { studio_generation_status?: string; [key: string]: unknown }
}

export function isKeepAwakeEnabled(storage?: Pick<Storage, 'getItem'> | null): boolean {
  const raw = (storage ?? localStorage).getItem(KEEP_AWAKE_SETTING_KEY)
  if (raw === null || raw === undefined || raw === '') return true
  return raw === '1' || raw === 'true'
}

export function setKeepAwakeEnabled(
  on: boolean,
  storage?: Pick<Storage, 'setItem'> | null,
): void {
  (storage ?? localStorage).setItem(KEEP_AWAKE_SETTING_KEY, on ? '1' : '0')
}

/** Spec: screening / production / rendering, plus DB processing|pending. */
export function projectIsProducing(project: KeepAwakeProjectLike): boolean {
  const status = String(project.status || '')
  if (status === 'processing' || status === 'pending') return true
  const gen = String(
    project.settings?.studio_generation_status
      || project.processing_config?.studio_generation_status
      || '',
  )
  return RUNNING_GENERATION.has(gen)
}

export function anyProjectProducing(projects: KeepAwakeProjectLike[]): boolean {
  return projects.some(projectIsProducing)
}

type InvokeFn = (cmd: string, args?: { on: boolean }) => Promise<unknown>

export type KeepAwakeControllerOptions = {
  invoke?: InvokeFn
  /** Desktop-only; when false, never call native. */
  isDesktop?: () => boolean | Promise<boolean>
  now?: () => number
  setTimeout?: (fn: () => void, ms: number) => ReturnType<typeof setTimeout>
  clearTimeout?: (id: ReturnType<typeof setTimeout>) => void
  releaseDelayMs?: number
  retryBackoffMs?: readonly number[]
  getEnabled?: () => boolean
  storage?: Pick<Storage, 'getItem' | 'setItem'>
}

/**
 * Multi-source producing signals → one native keep-awake command at a time.
 * Commands are serialized. A late result never overwrites a newer decision.
 */
export function createKeepAwakeController(options: KeepAwakeControllerOptions = {}) {
  const sources = new Map<string, boolean>()
  let lock: KeepAwakeLockState = 'released'
  let generation = 0
  let chain: Promise<void> = Promise.resolve()
  let queued = false
  let queuedOn: boolean | null = null
  let releaseTimer: ReturnType<typeof setTimeout> | null = null
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  let retryAttempt = 0
  let lastFailureAt = 0
  const listeners = new Set<(show: boolean) => void>()

  const releaseDelayMs = options.releaseDelayMs ?? KEEP_AWAKE_RELEASE_DELAY_MS
  const backoff = options.retryBackoffMs ?? KEEP_AWAKE_RETRY_BACKOFF_MS
  const schedule = options.setTimeout ?? ((fn, ms) => setTimeout(fn, ms))
  const cancel = options.clearTimeout ?? ((id) => clearTimeout(id))
  const storage = options.storage
  const getEnabled = options.getEnabled ?? (() => isKeepAwakeEnabled(storage))
  const now = options.now ?? (() => Date.now())

  const anySource = () => [...sources.values()].some(Boolean)
  const wantOn = () => anySource() && getEnabled()
  const activityVisible = () => anySource() && lock === 'held' && getEnabled()

  const notify = () => {
    const show = activityVisible()
    for (const listener of listeners) listener(show)
  }

  const clearTimer = (kind: 'release' | 'retry') => {
    if (kind === 'release' && releaseTimer !== null) {
      cancel(releaseTimer)
      releaseTimer = null
    }
    if (kind === 'retry' && retryTimer !== null) {
      cancel(retryTimer)
      retryTimer = null
    }
  }

  const scheduleRetry = () => {
    if (retryAttempt >= backoff.length) {
      lastFailureAt = now()
      return
    }
    const delay = backoff[retryAttempt]
    retryAttempt += 1
    const scheduledGen = generation
    retryTimer = schedule(() => {
      retryTimer = null
      if (generation !== scheduledGen) return
      kick(true)
    }, delay)
  }

  const kick = (fromRetry = false) => {
    const want = wantOn()
    if ((queued || retryTimer !== null) && queuedOn === want) return
    if (!queued && retryTimer === null && want && lock === 'held') return
    if (!queued && retryTimer === null && !want && lock === 'released') return
    if (!fromRetry && !queued && retryTimer === null && lock === 'unknown' && queuedOn === want && retryAttempt >= backoff.length) {
      const cap = backoff[backoff.length - 1] ?? 0
      if (now() - lastFailureAt < cap) return
      retryAttempt = 0
    }

    clearTimer('retry')
    queued = true
    queuedOn = want
    const gen = ++generation
    const run = async () => {
      try {
        if (gen !== generation) return
        const desired = wantOn()
        if (desired && lock === 'held') return
        if (!desired && lock === 'released') return
        try {
          let desktop = true
          if (options.isDesktop) desktop = Boolean(await options.isDesktop())
          if (gen !== generation) {
            lock = 'unknown'
            notify()
            return
          }
          if (desktop && options.invoke) await options.invoke('set_keep_awake', { on: desired })
          if (gen !== generation) {
            lock = 'unknown'
            notify()
            return
          }
          lock = desired ? 'held' : 'released'
          retryAttempt = 0
          lastFailureAt = 0
          notify()
        } catch (err) {
          console.warn('[keepAwake] set_keep_awake failed', err)
          if (gen !== generation) {
            lock = 'unknown'
            notify()
            return
          }
          lock = 'unknown'
          notify()
          scheduleRetry()
        }
      } finally {
        if (gen === generation) queued = false
      }
    }
    chain = chain.then(run, run)
  }

  const recompute = () => {
    if (!getEnabled() || anySource()) {
      clearTimer('release')
      kick()
      return
    }
    if (queued) {
      kick()
      return
    }
    if (lock === 'held') {
      if (releaseTimer !== null) return
      releaseTimer = schedule(() => {
        releaseTimer = null
        if (anySource() || !getEnabled()) return
        kick()
      }, releaseDelayMs)
      return
    }
    if (lock === 'unknown') kick()
  }

  return {
    /** Report whether a named source (e.g. `projects`, `workspace:id`) is producing. */
    setSource(id: string, producing: boolean) {
      if (!producing) {
        if (!sources.has(id)) return
        sources.delete(id)
      } else {
        sources.set(id, true)
      }
      recompute()
    },
    /** Replace only the projects-list source. Other mounted sources stay. */
    syncProjects(projects: KeepAwakeProjectLike[]) {
      const producing = anyProjectProducing(projects)
      if (!producing) {
        const hadList = sources.has('projects')
        if (hadList) sources.delete('projects')
        // An idle list must not erase workspace/statusbar sources. It may still
        // retry a release whose previous command failed.
        if (!hadList && lock !== 'unknown') return
      } else {
        sources.set('projects', true)
      }
      recompute()
    },
    /** Settings toggle flipped — re-evaluate immediately. */
    onEnabledChange(enabled: boolean) {
      setKeepAwakeEnabled(enabled, storage)
      if (!enabled) {
        clearTimer('release')
        kick()
      } else {
        recompute()
      }
    },
    /** Confirmed native lock. Unknown is not held and is not a claim that sleep is allowed. */
    isHeld() {
      return lock === 'held'
    },
    lockState(): KeepAwakeLockState {
      return lock
    },
    /** Header pill: a source is active and the native lock was confirmed. */
    showsActivityLock() {
      return activityVisible()
    },
    subscribe(listener: (show: boolean) => void) {
      listeners.add(listener)
      return () => { listeners.delete(listener) }
    },
    /** Test helper: flush pending invoke chain. */
    async flush() {
      await chain
    },
    /** Test helper. */
    getSources() {
      return new Map(sources)
    },
  }
}

export type KeepAwakeController = ReturnType<typeof createKeepAwakeController>

let singleton: KeepAwakeController | null = null

export function getKeepAwakeController(): KeepAwakeController {
  if (!singleton) {
    singleton = createKeepAwakeController({
      invoke: async (cmd, args) => {
        const { invoke } = await import('@tauri-apps/api/core')
        return invoke(cmd, args)
      },
      isDesktop: async () => {
        const { isDesktopMode } = await import('../../utils/desktopMode')
        return isDesktopMode()
      },
    })
  }
  return singleton
}

/** Reset singleton (tests). */
export function __resetKeepAwakeControllerForTests() {
  singleton = null
}
