/** #418 rewrite: the one install-recovery controller for the import page and the confirm page.
 *
 * Install, download, done, failed and timeout are distinct phases. The controller is opened from a coded backend
 * refusal (or a readiness check), drives runtime install -> model download itself, and ends in exactly one of:
 * `ready`, `failed` or `timeout` (retry, or open transcription settings). When a wait it was polling reaches `ready`
 * it calls `onReady` once, so the page continues the same import / confirmation by itself (#232); the continue button
 * stays as the exit for a `ready` that was not reached by waiting. It never switches provider.
 * Polls read enums and numbers only (no model paths, no user content). */
import type { ReadinessCheck, ImportReadiness } from './importReadiness'
import { OFFLINE_MS, observe, startClock, STALL_MS, type Clock } from './recoveryClock'

export type RecoveryPhase = 'idle' | 'install_required' | 'installing' | 'downloading' | 'ready' | 'failed' | 'timeout'
/** `background`: an install the page started by itself (link import without whisper, #371); the page shows it
 * inline and the dialog stays closed until a submit is blocked on it. */
export interface RecoveryState {
  phase: RecoveryPhase; percent: number | null; model?: string; background?: boolean
  /** #403: readiness has gone unanswered (network error / timeout, no HTTP response) since `offlineSince`; polling
   * goes on. Derived for the view, never stored. */
  unreachable?: boolean
  /** #403: `failed` because the backend was unreachable for OFFLINE_MS; low-frequency polls continue the wait
   * by themselves once the backend answers again. Derived for the view, never stored. */
  offline?: boolean
}

export interface RecoveryApi {
  /** One readiness request (studioApi.readinessProbe): no retry, a 5s timeout that aborts it, and the round's signal
   * cancels it. A rejection with an HTTP response (even a 500) is an answer; without one the backend is unreachable. */
  readiness: (signal: AbortSignal) => Promise<ImportReadiness | null>
  /** The follow-up reads take the round's signal too and are called like the probe (probeConfig). */
  getRuntimeStatus: (signal: AbortSignal) => Promise<{ status?: string; progress?: number }>
  getModels: (signal: AbortSignal) => Promise<{ name: string; status?: string; downloadProgress?: number | null }[]>
  /** The round's signal: axios cancels the wait. A request the backend already accepted is not revoked. */
  installRuntime: (signal: AbortSignal) => Promise<unknown>
  downloadModel: (model: string, signal: AbortSignal) => Promise<unknown>
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
  /** Monotonic clock (default performance.now()); tests inject a fake one. */
  now?: () => number
  /** The page's poll cadence while waiting (the cap of one observation, recoveryClock.ts). */
  pollMs?: number
  /** A wait reached ready: continue with this fresh report (the page must not reuse its cached readiness, #349). */
  onReady?: (report: ImportReadiness | null) => void
  /** Every readiness report the controller read, so the page's readiness is never older than the controller's. */
  onReport?: (report: ImportReadiness) => void
}
export { OFFLINE_MS, STALL_MS }
/** #403: poll interval once failed for being offline (the wait continues by itself when the backend is back). */
export const OFFLINE_RETRY_MS = 10 * 1000
/** Poll interval while installing / downloading. */
export const POLL_MS = 2 * 1000
/** Timeout of every read of a round (axios aborts the request). */
export const READINESS_TIMEOUT_MS = 5 * 1000
/** The axios config of every read of a round: the round's signal, READINESS_TIMEOUT_MS, a single attempt. */
export const probeConfig = (signal: AbortSignal) => ({ signal, timeout: READINESS_TIMEOUT_MS, retry: false as const })

/** #403: only a network error (no HTTP response: refused, reset, timed out) means the backend is unreachable.
 * An HTTP error such as a readiness 500 is a reachable backend. */
export function isNetworkError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return true
  const response = (error as { response?: unknown }).response
  return response === undefined || response === null
}

type Waiting = 'installing' | 'downloading'
/** What a round may write at its end. */
interface Next { view: RecoveryState; clock: Clock; resume: Waiting; ownsInstall: boolean; report?: ImportReadiness | null; ready?: boolean }
interface Round { ctrl: AbortController; running: Promise<RecoveryState> | null }
/** Thrown by step() when the round ended; runRound drops the round without writing anything. */
const ABORTED = { aborted: true }

export function createRecoveryController(api: RecoveryApi, options: ControllerOptions = {}) {
  const stallMs = options.stallMs ?? STALL_MS
  const now = options.now ?? (() => typeof performance !== 'undefined' ? performance.now() : Date.now())
  const pollMs = options.pollMs ?? POLL_MS
  let state: RecoveryState = { phase: 'idle', percent: null }
  let clock: Clock = startClock(now()) // the only timing state (recoveryClock.ts)
  let resume: Waiting = 'installing'
  let ownsInstall = false // this controller started the install: it carries the runtime on to the model download
  const listeners = new Set<(s: RecoveryState) => void>()
  const offlineFailed = () => state.phase === 'failed' && clock.unanswered
  const view = (raw: RecoveryState, unanswered: boolean): RecoveryState => {
    const { unreachable: _u, offline: _o, ...rest } = raw
    void _u; void _o
    if (!unanswered) return rest
    if (rest.phase === 'failed') return { ...rest, offline: true, unreachable: true }
    if (rest.phase === 'installing' || rest.phase === 'downloading') return { ...rest, unreachable: true }
    return rest
  }
  /** Writes the state (open / close / install / round results). */
  const publish = (raw: RecoveryState) => {
    const merged = state.background && raw.background === undefined && raw.phase !== 'idle' ? { ...raw, background: true } : raw
    state = view(merged, clock.unanswered)
    listeners.forEach(fn => fn(state))
  }
  const newRound = (): Round => ({ ctrl: new AbortController(), running: null })
  let current = newRound()
  /** open / close / install / retry: the old round is aborted (its requests are cancelled) and a new one starts. */
  const startRound = () => { current.ctrl.abort(); current = newRound(); clock = startClock(now()); ownsInstall = false; return current }
  /** The one write of a round's result. stepsettling and this write are several microtasks apart
   * (probe -> runRound, fromCheck -> runRound); a close() / dispose() in between is stopped only here. */
  const commit = (signal: AbortSignal, next: Next) => {
    if (signal.aborted) return
    if (next.report && options.onReport) options.onReport(next.report)
    clock = next.clock; resume = next.resume; ownsInstall = next.ownsInstall
    publish(next.view)
    if (next.ready && options.onReady) options.onReady(next.report ?? null) // #232: continue by itself, once
  }
  /** Every request of a round goes through here. the round is checked before the request is made, and the
   * round stops at once when it ends while waiting (no state, no callbacks). */
  const step = <T>(signal: AbortSignal, request: () => Promise<T>): Promise<T> => new Promise<T>((resolve, reject) => {
    if (signal.aborted) { reject(ABORTED); return }
    const onAbort = () => reject(ABORTED)
    signal.addEventListener('abort', onAbort, { once: true })
    request().then(
      value => { signal.removeEventListener('abort', onAbort); if (signal.aborted) reject(ABORTED); else resolve(value) },
      error => { signal.removeEventListener('abort', onAbort); reject(signal.aborted ? ABORTED : error) },
    )
  })
  const fromCheck = async (signal: AbortSignal, check: ReadinessCheck | null | undefined, base: RecoveryState, owns: boolean): Promise<{ view: RecoveryState; owns: boolean }> => {
    if (!check || check.ok) return { view: { phase: 'ready', percent: 100 }, owns }
    const model = check.model ?? base.model
    if (check.code === 'whisper_not_installed' && owns) {
      // #350: our install request was accepted but the backend has not reported it yet -> still installing.
      return { view: { phase: 'installing', percent: base.percent, model }, owns }
    }
    if (check.code === 'whisper_installing') {
      const runtime = await step(signal, () => api.getRuntimeStatus(signal)).catch(error => { if (error === ABORTED) throw error; return null })
      if (runtime?.status === 'error') return { view: { phase: 'failed', percent: null, model }, owns }
      return { view: { phase: 'installing', percent: runtime ? clamp(runtime.progress) : base.percent, model }, owns }
    }
    if (check.code === 'whisper_model_downloading') {
      const models = await step(signal, () => api.getModels(signal)).catch(error => { if (error === ABORTED) throw error; return null })
      const row = models?.find(item => item.name === check.model)
      if (row?.status === 'error') return { view: { phase: 'failed', percent: null, model }, owns }
      return { view: { phase: 'downloading', percent: models ? clamp(row?.downloadProgress) : base.percent, model }, owns }
    }
    if (check.code === 'whisper_model_missing' && owns && base.phase === 'downloading') {
      // #372: our accepted download has not shown up in readiness yet: still downloading, the request is not resent.
      return { view: { phase: 'downloading', percent: base.percent ?? 0, model }, owns }
    }
    if (check.code === 'whisper_model_missing' && owns && check.model) {
      // The runtime is in; the install this controller started goes on to the model (#281). #372: only an accepted
      // request enters downloading; a 500 or a network error is failed (retry sends it again, polling never does).
      try { await step(signal, () => api.downloadModel(check.model as string, signal)) } catch (error) {
        if (error === ABORTED) throw error
        return { view: { phase: 'failed', percent: null, model: check.model }, owns: false }
      }
      return { view: { phase: 'downloading', percent: 0, model: check.model }, owns }
    }
    return { view: { phase: phaseOfCode(check.code), percent: null, model }, owns }
  }
  /** the one timing input of a round, taken right before its one commit. The cap uses the waiting cadence
   * (pollMs): once failed for being offline the counts decide nothing (only an answer resumes the wait). */
  const tick = (answered: boolean, progressed: boolean) => observe(clock,
    { now: now(), answered, progressed, pollMs, readTimeoutMs: READINESS_TIMEOUT_MS },
    { offlineMs: OFFLINE_MS, stallMs })
  /** The one serial reader of a round: probe, then the install request or the follow-up reads, then one commit. */
  const runRound = async (round: Round, kind: 'install' | 'poll'): Promise<RecoveryState> => {
    const signal = round.ctrl.signal
    try {
      let report: ImportReadiness | null = null
      let answered = true
      try { report = await step(signal, () => api.readiness(signal)) } catch (error) { if (error === ABORTED) throw error; answered = !isNetworkError(error) }
      if (kind === 'install') {
        const check = report?.checks?.transcription
        const model = check?.model ?? state.model
        const toModel = !!(check && String(check.code).startsWith('whisper_model') && model)
        try {
          await step(signal, () => toModel ? api.downloadModel(model as string, signal) : api.installRuntime(signal))
          commit(signal, { view: { phase: toModel ? 'downloading' : 'installing', percent: toModel ? 0 : null, model: toModel ? model : state.model }, clock: tick(true, true).clock, resume, ownsInstall: true, report })
        } catch (error) {
          if (error === ABORTED) throw error
          commit(signal, { view: { phase: 'failed', percent: null, model: state.model }, clock: tick(true, true).clock, resume, ownsInstall: false, report })
        }
        return state
      }
      if (!answered) {
        const { clock: next, outcome } = tick(false, false)
        // Once failed for being offline only an answer changes anything (it resumes the wait).
        if (offlineFailed() || outcome === 'continue') { commit(signal, { view: state, clock: next, resume, ownsInstall }); return state }
        if (outcome === 'timeout') { commit(signal, { view: { ...state, phase: 'timeout' }, clock: next, resume, ownsInstall }); return state }
        // #403 offline: unreachable for OFFLINE_MS of counted time -> failed (retry offered); slow polls go on.
        commit(signal, { view: { ...state, phase: 'failed', percent: null }, clock: next, resume: state.phase === 'downloading' ? 'downloading' : 'installing', ownsInstall })
        return state
      }
      // Any answer (200 or a 500) ends `unreachable`; an offline failure resumes the interrupted wait by itself.
      const base: RecoveryState = offlineFailed() ? { ...state, phase: resume } : state
      const next = report ? await fromCheck(signal, report.checks?.transcription, base, ownsInstall) : { view: { ...base }, owns: ownsInstall }
      const wasWaiting = base.phase === 'installing' || base.phase === 'downloading'
      let nextView = next.view
      const { clock: counted, outcome } = tick(true, nextView.percent !== state.percent || nextView.phase !== state.phase)
      if ((nextView.phase === 'installing' || nextView.phase === 'downloading') && outcome === 'timeout') nextView = { ...nextView, phase: 'timeout' }
      commit(signal, { view: nextView, clock: counted, resume, ownsInstall: next.owns, report, ready: wasWaiting && nextView.phase === 'ready' })
      return state
    } catch (error) {
      if (error === ABORTED) return state // the round ended: nothing is written
      throw error
    }
  }
  const run = (round: Round, kind: 'install' | 'poll') => {
    const p = runRound(round, kind).finally(() => { if (round.running === p) round.running = null })
    round.running = p
    return p
  }
  const controller = {
    get state() { return state },
    subscribe(fn: (s: RecoveryState) => void) { listeners.add(fn); return () => { listeners.delete(fn) } },
    /** Open from a coded refusal. */
    open(code: string, model?: string) {
      // A blocked submit opens the dialog; a background install it lands on keeps running (#371).
      const waiting = state.background && (state.phase === 'installing' || state.phase === 'downloading')
      if (waiting) { publish({ ...state, background: false }); return }
      startRound()
      publish({ phase: phaseOfCode(code), percent: null, model, background: false })
    },
    close() { startRound(); publish({ phase: 'idle', percent: null, background: false }) },
    /** One-click install: runtime, then the model, without leaving the dialog. #350: the request goes out first;
     * the waiting phase (and its polls) starts only once it was accepted. Polls meanwhile share this round. */
    async install(opts: { background?: boolean } = {}) {
      const round = startRound()
      const background = opts.background ?? false
      if (state.background !== background) state = { ...state, background }
      await run(round, 'install')
    },
    /** Retry after failed / timeout: same path as install (a new round, the unreachable time starts over). */
    async retry() { await controller.install() },
    /** One poll; returns the new state. Waiting phases time out after stallMs of observed time without progress.
     * A round already reading is shared, never doubled.*/
    poll(): Promise<RecoveryState> {
      const round = current
      if (round.ctrl.signal.aborted) return Promise.resolve(state)
      if (round.running) return round.running
      if (state.phase !== 'installing' && state.phase !== 'downloading' && !offlineFailed()) return Promise.resolve(state)
      return run(round, 'poll')
    },
    /** The page unmounted: the round is aborted (requests cancelled); no state, no onReady after this. */
    dispose() { current.ctrl.abort(); listeners.clear() },
    /** The page (re)mounted the same controller (React StrictMode runs effects twice): a disposed controller gets a
     * fresh round, so polling continues; the state is kept. */
    activate() { if (current.ctrl.signal.aborted) { current = newRound(); clock = { ...clock, lastAt: now() } } },
  }
  return controller
}

export type RecoveryController = ReturnType<typeof createRecoveryController>
