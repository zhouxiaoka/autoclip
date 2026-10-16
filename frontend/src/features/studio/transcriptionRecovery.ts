/** #418 rewrite: the one install-recovery controller for the import page and the confirm page.
 *
 * Install, download, done, failed and timeout are distinct phases. The controller is opened from a coded backend
 * refusal (or a readiness check), drives runtime install -> model download itself, and ends in exactly one of:
 * `ready`, `failed` or `timeout` (retry, or open transcription settings). When a wait it was polling reaches `ready`
 * it calls `onReady` once, so the page continues the same import / confirmation by itself (#232); the continue button
 * stays as the exit for a `ready` that was not reached by waiting. It never switches provider.
 * Polls read enums and numbers only (no model paths, no user content). */
import type { ReadinessCheck, ImportReadiness } from './importReadiness'

export type RecoveryPhase = 'idle' | 'install_required' | 'installing' | 'downloading' | 'ready' | 'failed' | 'timeout'
/** `background`: an install the page started by itself (link import without whisper, #371); the page shows it
 * inline and the dialog stays closed until a submit is blocked on it. */
export interface RecoveryState {
  phase: RecoveryPhase; percent: number | null; model?: string; background?: boolean
  /** #403: the last readiness poll could not reach the backend (network error, no HTTP response); polling goes on. */
  unreachable?: boolean
  /** #403: `failed` because the backend was unreachable for OFFLINE_MS; low-frequency polls continue the wait
   * by themselves once the backend answers again. */
  offline?: boolean
}

export interface RecoveryApi {
  readiness: () => Promise<ImportReadiness | null>
  getRuntimeStatus: () => Promise<{ status?: string; progress?: number }>
  getModels: () => Promise<{ name: string; status?: string; downloadProgress?: number | null }[]>
  installRuntime: () => Promise<unknown>
  downloadModel: (model: string) => Promise<unknown>
}

export const RECOVERY_CODES = ['whisper_not_installed', 'whisper_install_failed', 'whisper_model_missing', 'whisper_model_failed', 'whisper_installing', 'whisper_model_downloading'] as const
export function isRecoveryCode(code: string | null | undefined): boolean {
  return !!code && (RECOVERY_CODES as readonly string[]).includes(code)
}

/** Phase of a transcription check code (readiness report or coded 422). */
export function phaseOfCode(code: string | null | undefined): RecoveryPhase {
  if (code === 'whisper_installing') return 'installing'
  if (code === 'whisper_model_downloading') return 'downloading'
  if (code === 'whisper_install_failed' || code === 'whisper_model_failed') return 'failed'
  if (code === 'whisper_not_installed' || code === 'whisper_model_missing') return 'install_required'
  return 'idle'
}

const clamp = (value: unknown) => typeof value === 'number' && isFinite(value) ? Math.max(0, Math.min(100, Math.round(value))) : null

export interface ControllerOptions {
  stallMs?: number
  now?: () => number
  /** A wait reached ready: continue with this fresh report (the page must not reuse its cached readiness, #349). */
  onReady?: (report: ImportReadiness | null) => void
  /** Every readiness report the controller read, so the page's readiness is never older than the controller's. */
  onReport?: (report: ImportReadiness) => void
}
export const STALL_MS = 10 * 60 * 1000
/** #403: continuous time the backend must be unreachable (network errors only) before a wait is failed. */
export const OFFLINE_MS = 30 * 1000
/** #403: poll interval once failed for being offline (the wait continues by itself when the backend is back). */
export const OFFLINE_RETRY_MS = 10 * 1000

/** #403: only a network error (no HTTP response: refused, reset, timed out) means the backend is unreachable.
 * An HTTP error such as a readiness 500 is a reachable backend. */
export function isNetworkError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return true
  const response = (error as { response?: unknown }).response
  return response === undefined || response === null
}

export function createRecoveryController(api: RecoveryApi, options: ControllerOptions = {}) {
  const stallMs = options.stallMs ?? STALL_MS
  const now = options.now ?? (() => Date.now())
  let state: RecoveryState = { phase: 'idle', percent: null }
  let installing = false // this controller started the install: carry it on to the model download
  let modelRequested = false // #372: the model download request went out and was accepted; never resend it by polling
  let unreachableSince: number | null = null // #403: start of the current unreachable streak (network errors only)
  let resumePhase: RecoveryPhase = 'installing' // #403: the wait an offline failure interrupted
  let progressAt = now()
  const listeners = new Set<(s: RecoveryState) => void>()
  const set = (raw: RecoveryState) => {
    const next = state.background && raw.background === undefined && raw.phase !== 'idle' ? { ...raw, background: true } : raw
    if (next.percent !== state.percent || next.phase !== state.phase) progressAt = now()
    state = next
    listeners.forEach(fn => fn(state))
  }
  const read = async () => {
    let report: ImportReadiness | null = null
    let unreachable = false
    try { report = await api.readiness() } catch (error) { unreachable = isNetworkError(error) }
    if (unreachable) { if (unreachableSince === null) unreachableSince = now() } else unreachableSince = null
    if (report && options.onReport) options.onReport(report)
    return report
  }
  const fromCheck = async (check: ReadinessCheck | null | undefined): Promise<RecoveryState> => {
    if (!check || check.ok) return { phase: 'ready', percent: 100 }
    const model = check.model ?? state.model
    if (check.code === 'whisper_not_installed' && installing) {
      // #350: our install request was accepted but the backend has not reported it yet -> still installing.
      return { phase: 'installing', percent: state.percent, model }
    }
    if (check.code === 'whisper_installing') {
      const runtime = await api.getRuntimeStatus().catch(() => null)
      if (runtime?.status === 'error') return { phase: 'failed', percent: null, model }
      return { phase: 'installing', percent: clamp(runtime?.progress), model }
    }
    if (check.code === 'whisper_model_downloading') {
      const models = await api.getModels().catch(() => null)
      const row = models?.find(item => item.name === check.model)
      if (row?.status === 'error') return { phase: 'failed', percent: null, model }
      return { phase: 'downloading', percent: clamp(row?.downloadProgress), model }
    }
    if (check.code === 'whisper_model_missing' && installing && modelRequested) {
      // Our accepted download has not shown up in readiness yet: still downloading, and the request is not resent.
      return { phase: 'downloading', percent: state.percent ?? 0, model }
    }
    if (check.code === 'whisper_model_missing' && installing && check.model) {
      // The runtime is in; the install this controller started goes on to the model (#281). #372: only an accepted
      // request enters downloading; a 500 or a network error is failed (retry sends it again, polling never does).
      try {
        await api.downloadModel(check.model)
      } catch {
        installing = false
        return { phase: 'failed', percent: null, model: check.model }
      }
      modelRequested = true
      return { phase: 'downloading', percent: 0, model: check.model }
    }
    return { phase: phaseOfCode(check.code), percent: null, model }
  }
  const controller = {
    get state() { return state },
    subscribe(fn: (s: RecoveryState) => void) { listeners.add(fn); return () => { listeners.delete(fn) } },
    /** Open from a coded refusal. */
    open(code: string, model?: string) {
      // A blocked submit opens the dialog; a background install it lands on keeps running (#371).
      const waiting = state.background && (state.phase === 'installing' || state.phase === 'downloading')
      if (waiting) { set({ ...state, background: false }); return }
      installing = false; modelRequested = false
      set({ phase: phaseOfCode(code), percent: null, model, background: false })
    },
    close() { installing = false; modelRequested = false; set({ phase: 'idle', percent: null, background: false }) },
    /** One-click install: runtime, then the model, without leaving the dialog. */
    async install(opts: { background?: boolean } = {}) {
      // #350: the request goes out first; the waiting phase (and its polls) starts only once it was accepted.
      installing = false; modelRequested = false; unreachableSince = null
      const background = opts.background ?? false
      if (state.background !== background) state = { ...state, background }
      const report = await read()
      const check = report?.checks?.transcription
      try {
        if (check && String(check.code).startsWith('whisper_model')) {  // runtime is in: (re)start the model download
          const model = check.model ?? state.model
          if (model) { await api.downloadModel(model); installing = true; modelRequested = true; set({ phase: 'downloading', percent: 0, model }); return }
        }
        await api.installRuntime()
        installing = true
        set({ phase: 'installing', percent: null, model: state.model })
      } catch {
        installing = false
        set({ phase: 'failed', percent: null, model: state.model })
      }
    },
    /** Retry after failed / timeout: same path as install. */
    async retry() { await controller.install() },
    /** One poll; returns the new state. Waiting phases time out after stallMs without progress. */
    async poll(): Promise<RecoveryState> {
      const offlineFailed = state.phase === 'failed' && !!state.offline
      if (state.phase !== 'installing' && state.phase !== 'downloading' && !offlineFailed) return state
      const report = await read()
      if (offlineFailed) {
        // #403: the backend answers again -> the interrupted wait continues by itself (no click needed).
        if (!report) return state
        state = { ...state, phase: resumePhase, offline: undefined, unreachable: undefined }
        progressAt = now()
      }
      if (unreachableSince !== null && now() - unreachableSince >= OFFLINE_MS) {
        // #403 offline: unreachable for OFFLINE_MS in a row -> failed (retry offered); low-frequency polls go on.
        resumePhase = state.phase
        set({ ...state, phase: 'failed', percent: null, offline: true, unreachable: true })
        return state
      }
      const base = { ...state, unreachable: unreachableSince !== null ? true : undefined }
      const next = report ? await fromCheck(report.checks?.transcription) : base
      if ((next.phase === 'installing' || next.phase === 'downloading') && next.percent === state.percent && next.phase === state.phase
        && now() - progressAt >= stallMs) {
        set({ ...next, phase: 'timeout' })
        return state
      }
      const waited = state.phase === 'installing' || state.phase === 'downloading'
      set(next)
      if (waited && next.phase === 'ready' && options.onReady) options.onReady(report)  // #232: continue by itself
      return state
    },
  }
  return controller
}

export type RecoveryController = ReturnType<typeof createRecoveryController>
