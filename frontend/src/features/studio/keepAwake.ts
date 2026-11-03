/**
 * System keep-awake while any project is producing.
 * Hold immediately on running; release 10s after none remain.
 * Setting 「制作时阻止电脑休眠」 defaults on (localStorage).
 */

export const KEEP_AWAKE_SETTING_KEY = 'autoclip.keep_awake.enabled.v1'
export const KEEP_AWAKE_RELEASE_DELAY_MS = 10_000

const RUNNING_GENERATION = new Set(['screening', 'production', 'rendering'])

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
  getEnabled?: () => boolean
  storage?: Pick<Storage, 'getItem' | 'setItem'>
}

/**
 * Multi-source producing signals → idempotent native keep-awake with delayed release.
 */
export function createKeepAwakeController(options: KeepAwakeControllerOptions = {}) {
  const sources = new Map<string, boolean>()
  let held = false
  let releaseTimer: ReturnType<typeof setTimeout> | null = null
  let pendingInvoke: Promise<void> = Promise.resolve()
  const listeners = new Set<(held: boolean) => void>()

  const releaseDelayMs = options.releaseDelayMs ?? KEEP_AWAKE_RELEASE_DELAY_MS
  const schedule = options.setTimeout ?? ((fn, ms) => setTimeout(fn, ms))
  const cancel = options.clearTimeout ?? ((id) => clearTimeout(id))
  const storage = options.storage
  const getEnabled = options.getEnabled ?? (() => isKeepAwakeEnabled(storage))

  const notify = () => {
    for (const listener of listeners) listener(held)
  }

  const applyNative = (on: boolean) => {
    if (held === on) return pendingInvoke
    // Optimistic UI + tray: mark held before the native round-trip so the
    // status-bar pill appears immediately; roll back only if invoke fails.
    const previous = held
    held = on
    notify()
    const run = async () => {
      try {
        let desktop = true
        if (options.isDesktop) {
          desktop = Boolean(await options.isDesktop())
        }
        if (!desktop) return
        if (options.invoke) {
          await options.invoke('set_keep_awake', { on })
        }
      } catch (err) {
        console.warn('[keepAwake] set_keep_awake failed', err)
        if (held === on) {
          held = previous
          notify()
        }
      }
    }
    pendingInvoke = pendingInvoke.then(run, run)
    return pendingInvoke
  }

  const clearReleaseTimer = () => {
    if (releaseTimer !== null) {
      cancel(releaseTimer)
      releaseTimer = null
    }
  }

  const recompute = () => {
    const anyRunning = [...sources.values()].some(Boolean)
    if (!getEnabled()) {
      clearReleaseTimer()
      void applyNative(false)
      return
    }
    if (anyRunning) {
      clearReleaseTimer()
      void applyNative(true)
      return
    }
    if (!held && releaseTimer === null) return
    if (releaseTimer !== null) return
    releaseTimer = schedule(() => {
      releaseTimer = null
      if ([...sources.values()].some(Boolean) || !getEnabled()) return
      void applyNative(false)
    }, releaseDelayMs)
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
    /** Replace the projects-list source from a snapshot. */
    syncProjects(projects: KeepAwakeProjectLike[]) {
      const producing = anyProjectProducing(projects)
      if (!producing) {
        if (sources.has('projects')) {
          sources.delete('projects')
          recompute()
        }
      } else {
        sources.set('projects', true)
        recompute()
      }
    },
    /** Settings toggle flipped — re-evaluate immediately. */
    onEnabledChange(enabled: boolean) {
      setKeepAwakeEnabled(enabled, storage)
      if (!enabled) {
        clearReleaseTimer()
        void applyNative(false)
      } else {
        recompute()
      }
    },
    isHeld() {
      return held
    },
    subscribe(listener: (held: boolean) => void) {
      listeners.add(listener)
      return () => { listeners.delete(listener) }
    },
    /** Test helper: flush pending invoke chain. */
    async flush() {
      await pendingInvoke
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
