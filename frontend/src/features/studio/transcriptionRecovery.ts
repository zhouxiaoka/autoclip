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
export interface RecoveryState { phase: RecoveryPhase; percent: number | null; model?: string; background?: boolean }

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
/** Consecutive unreachable readiness polls before an install wait is failed (offline, #372). */
export const OFFLINE_POLLS = 3

export function createRecoveryController(api: RecoveryApi, options: ControllerOptions = {}) {
  const stallMs = options.stallMs ?? STALL_MS
  const now = options.now ?? (() => Date.now())
  let state: RecoveryState = { phase: 'idle', percent: null }
  let installing = false // this controller started the install: carry it on to the model download
  let modelRequested = false // #372: the model download request went out and was accepted; never resend it by polling
  let readFailures = 0 // #372: consecutive polls that could not reach the backend (offline)
  let progressAt = now()
  const listeners = new Set<(s: RecoveryState) => void>()
  const set = (raw: RecoveryState) => {
    const next = state.background && raw.background === undefined && raw.phase !== 'idle' ? { ...raw, background: true } : raw
    if (next.percent !== state.percent || next.phase !== state.phase) progressAt = now()
    state = next
    listeners.forEach(fn => fn(state))
  }
  const read = async () => {
    const report = await api.readiness().catch(() => null)
    readFailures = report ? 0 : readFailures + 1
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
      installing = false; modelRequested = false; readFailures = 0
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
      if (state.phase !== 'installing' && state.phase !== 'downloading') return state
      const report = await read()
      if (!report && readFailures >= OFFLINE_POLLS) {
        // #372 offline: the backend cannot be reached -> failed, and retry is offered.
        installing = false; modelRequested = false
        set({ ...state, phase: 'failed', percent: null })
        return state
      }
      const next = report ? await fromCheck(report.checks?.transcription) : state
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
