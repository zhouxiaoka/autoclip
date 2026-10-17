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

/** #418 R27b I426: the controller's connection state, one explicit enum instead of flags.
 * - `checking`: not waiting on anything (idle / asked / ended), no readiness polling;
 * - `installing`: waiting on install / download, and the last readiness got an answer;
 * - `unreachable(startedAt)`: waiting, readiness unanswered since `startedAt`; the 30s timer lives only here;
 * - `failed_recoverable(resume)`: unreachable for OFFLINE_MS; slow polls resume `resume` once the backend answers;
 * - `ready`: a wait reached ready.
 * The view fields `unreachable` / `offline` on RecoveryState are derived from it, never set on their own. */
export type RecoveryLink =
  | { kind: 'checking' }
  | { kind: 'installing' }
  | { kind: 'unreachable'; startedAt: number }
  | { kind: 'failed_recoverable'; resume: 'installing' | 'downloading' }
  | { kind: 'ready' }

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
  /** Timer used for the readiness deadline (tests inject a clocked one). */
  setTimer?: (fn: () => void, ms: number) => unknown
  clearTimer?: (handle: unknown) => void
}
export const STALL_MS = 10 * 60 * 1000
/** #403: continuous time the backend must be unreachable (network errors only) before a wait is failed. */
export const OFFLINE_MS = 30 * 1000
/** #403: poll interval once failed for being offline (the wait continues by itself when the backend is back). */
export const OFFLINE_RETRY_MS = 10 * 1000
/** #418 R27b: deadline of one readiness request only (other requests keep their own timeouts). A backend that
 * accepts the connection but never answers (paused, hung) is unreachable, the same as a refused connection. */
export const READINESS_TIMEOUT_MS = 5 * 1000

/** The error a readiness request past READINESS_TIMEOUT_MS rejects with: no HTTP response, like axios' timeout. */
export function readinessTimeoutError(): Error {
  return Object.assign(new Error('readiness timeout'), { code: 'ECONNABORTED', response: undefined })
}

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
  let link: RecoveryLink = { kind: 'checking' }
  let installing = false // this controller started the install: carry it on to the model download
  let modelRequested = false // #372: the model download request went out and was accepted; never resend it by polling
  // #418 R27b I426: install / retry / open / close / dispose start a new round; a poll whose round no longer matches
  // is dropped (writes no state, calls no onReady). At most one poll is in flight (a second caller shares it).
  let round = 0
  let disposed = false
  let inflight: Promise<RecoveryState> | null = null
  let progressAt = now()
  const listeners = new Set<(s: RecoveryState) => void>()
  const view = (raw: RecoveryState): RecoveryState => {
    const { unreachable: _u, offline: _o, ...rest } = raw
    void _u; void _o
    if (link.kind === 'failed_recoverable') return { ...rest, offline: true, unreachable: true }
    if (link.kind === 'unreachable' && (rest.phase === 'installing' || rest.phase === 'downloading')) return { ...rest, unreachable: true }
    return rest
  }
  const set = (raw: RecoveryState) => {
    if (disposed) return
    const merged = state.background && raw.background === undefined && raw.phase !== 'idle' ? { ...raw, background: true } : raw
    if (merged.phase !== 'installing' && merged.phase !== 'downloading' && link.kind !== 'failed_recoverable') {
      link = merged.phase === 'ready' ? { kind: 'ready' } : { kind: 'checking' }
    }
    const next = view(merged)
    if (next.percent !== state.percent || next.phase !== state.phase) progressAt = now()
    state = next
    listeners.forEach(fn => fn(state))
  }
  const newRound = () => { round++; inflight = null; link = { kind: 'checking' } }
  const setTimer = options.setTimer ?? ((fn: () => void, ms: number) => setTimeout(fn, ms))
  const clearTimer = options.clearTimer ?? ((h: unknown) => clearTimeout(h as ReturnType<typeof setTimeout>))
  // #418 R27b: the readiness request is given READINESS_TIMEOUT_MS; a timeout counts toward OFFLINE_MS like a network error.
  const readinessWithDeadline = () => new Promise<ImportReadiness | null>((resolve, reject) => {
    let done = false
    const handle = setTimer(() => { if (!done) { done = true; reject(readinessTimeoutError()) } }, READINESS_TIMEOUT_MS)
    api.readiness().then(
      value => { if (!done) { done = true; clearTimer(handle); resolve(value) } },
      error => { if (!done) { done = true; clearTimer(handle); reject(error) } },
    )
  })
  /** One readiness read; `answered` is false only when the backend could not be reached (network error / timeout). */
  const read = async (): Promise<{ report: ImportReadiness | null; answered: boolean; sentAt: number }> => {
    const sentAt = now() // a timed-out request was unanswered since it went out, not since the deadline
    let report: ImportReadiness | null = null
    let answered = true
    try { report = await readinessWithDeadline() } catch (error) { answered = !isNetworkError(error) }
    return { report, answered, sentAt }
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
  const pollOnce = async (r: number): Promise<RecoveryState> => {
    const recoverable = link.kind === 'failed_recoverable'
    if (state.phase !== 'installing' && state.phase !== 'downloading' && !recoverable) return state
    const { report, answered, sentAt } = await read()
    if (r !== round || disposed) return state // I426: a stale round's answer is dropped
    if (report && options.onReport) options.onReport(report)
    if (link.kind === 'failed_recoverable') {
      // #403: the backend answers again -> the interrupted wait continues by itself (no click needed).
      if (!answered) return state
      const resume = link.resume
      link = { kind: 'installing' }
      set({ ...state, phase: resume })
      progressAt = now()
    } else if (!answered) {
      if (link.kind !== 'unreachable') link = { kind: 'unreachable', startedAt: sentAt }
      if (now() - link.startedAt >= OFFLINE_MS) {
        // #403 offline: unreachable for OFFLINE_MS in a row -> failed (retry offered); low-frequency polls go on.
        link = { kind: 'failed_recoverable', resume: state.phase === 'downloading' ? 'downloading' : 'installing' }
        set({ ...state, phase: 'failed', percent: null })
        return state
      }
      set({ ...state }) // shows "retrying"; leaves progress as it was
      return state
    } else {
      link = { kind: 'installing' } // any answer (200 or a 500) leaves `unreachable`: the timer is gone
    }
    const next = report ? await fromCheck(report.checks?.transcription) : { ...state }
    if (r !== round || disposed) return state
    if ((next.phase === 'installing' || next.phase === 'downloading') && next.percent === state.percent && next.phase === state.phase
      && now() - progressAt >= stallMs) {
      set({ ...next, phase: 'timeout' })
      return state
    }
    const waited = state.phase === 'installing' || state.phase === 'downloading'
    set(next)
    if (waited && next.phase === 'ready' && options.onReady) options.onReady(report)  // #232: continue by itself, once
    return state
  }
  const controller = {
    get state() { return state },
    get link(): RecoveryLink { return link },
    subscribe(fn: (s: RecoveryState) => void) { listeners.add(fn); return () => { listeners.delete(fn) } },
    /** Open from a coded refusal. */
    open(code: string, model?: string) {
      // A blocked submit opens the dialog; a background install it lands on keeps running (#371).
      const waiting = state.background && (state.phase === 'installing' || state.phase === 'downloading')
      if (waiting) { set({ ...state, background: false }); return }
      newRound(); installing = false; modelRequested = false
      set({ phase: phaseOfCode(code), percent: null, model, background: false })
    },
    close() { newRound(); installing = false; modelRequested = false; set({ phase: 'idle', percent: null, background: false }) },
    /** One-click install: runtime, then the model, without leaving the dialog. */
    async install(opts: { background?: boolean } = {}) {
      // #350: the request goes out first; the waiting phase (and its polls) starts only once it was accepted.
      newRound(); installing = false; modelRequested = false
      const r = round
      const background = opts.background ?? false
      if (state.background !== background) state = { ...state, background }
      const { report } = await read()
      if (r !== round || disposed) return
      if (report && options.onReport) options.onReport(report)
      const check = report?.checks?.transcription
      try {
        if (check && String(check.code).startsWith('whisper_model')) {  // runtime is in: (re)start the model download
          const model = check.model ?? state.model
          if (model) {
            await api.downloadModel(model)
            if (r !== round || disposed) return
            installing = true; modelRequested = true; link = { kind: 'installing' }; set({ phase: 'downloading', percent: 0, model }); return
          }
        }
        await api.installRuntime()
        if (r !== round || disposed) return
        installing = true; link = { kind: 'installing' }
        set({ phase: 'installing', percent: null, model: state.model })
      } catch {
        if (r !== round || disposed) return
        installing = false
        set({ phase: 'failed', percent: null, model: state.model })
      }
    },
    /** Retry after failed / timeout: same path as install (a new round, the unreachable timer starts over). */
    async retry() { await controller.install() },
    /** One poll; returns the new state. Waiting phases time out after stallMs without progress. A poll already in
     * flight is shared, never doubled (I426). */
    poll(): Promise<RecoveryState> {
      if (disposed) return Promise.resolve(state)
      if (inflight) return inflight
      const r = round
      const p = pollOnce(r).finally(() => { if (inflight === p) inflight = null })
      inflight = p
      return p
    },
    /** I426: the page unmounted. Answers still in flight are dropped; no state, no onReady after this. */
    dispose() { newRound(); disposed = true; listeners.clear() },
    /** The page (re)mounted the same controller (React StrictMode runs effects twice). */
    activate() { disposed = false },
  }
  return controller
}

export type RecoveryController = ReturnType<typeof createRecoveryController>
