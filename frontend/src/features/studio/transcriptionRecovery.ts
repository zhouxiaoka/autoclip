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
export interface RecoveryState { phase: RecoveryPhase; percent: number | null; model?: string }

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

export interface ControllerOptions { stallMs?: number; now?: () => number; onReady?: () => void }
export const STALL_MS = 10 * 60 * 1000

export function createRecoveryController(api: RecoveryApi, options: ControllerOptions = {}) {
  const stallMs = options.stallMs ?? STALL_MS
  const now = options.now ?? (() => Date.now())
  let state: RecoveryState = { phase: 'idle', percent: null }
  let installing = false // this controller started the install: carry it on to the model download
  let progressAt = now()
  const listeners = new Set<(s: RecoveryState) => void>()
  const set = (next: RecoveryState) => {
    if (next.percent !== state.percent || next.phase !== state.phase) progressAt = now()
    state = next
    listeners.forEach(fn => fn(state))
  }
  const fromCheck = async (check: ReadinessCheck | null | undefined): Promise<RecoveryState> => {
    if (!check || check.ok) return { phase: 'ready', percent: 100 }
    const model = check.model ?? state.model
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
    if (check.code === 'whisper_model_missing' && installing && check.model) {
      // The runtime is in; the install this controller started goes on to the model (#281).
      await api.downloadModel(check.model).catch(() => undefined)
      return { phase: 'downloading', percent: 0, model: check.model }
    }
    return { phase: phaseOfCode(check.code), percent: null, model }
  }
  const controller = {
    get state() { return state },
    subscribe(fn: (s: RecoveryState) => void) { listeners.add(fn); return () => { listeners.delete(fn) } },
    /** Open from a coded refusal. */
    open(code: string, model?: string) { installing = false; set({ phase: phaseOfCode(code), percent: null, model }) },
    close() { installing = false; set({ phase: 'idle', percent: null }) },
    /** One-click install: runtime, then the model, without leaving the dialog. */
    async install() {
      installing = true
      set({ phase: 'installing', percent: null, model: state.model })
      const report = await api.readiness().catch(() => null)
      const check = report?.checks?.transcription
      try {
        if (check && String(check.code).startsWith('whisper_model')) {  // runtime is in: (re)start the model download
          const model = check.model ?? state.model
          if (model) { await api.downloadModel(model); set({ phase: 'downloading', percent: 0, model }); return }
        }
        await api.installRuntime()
      } catch {
        set({ phase: 'failed', percent: null, model: state.model })
      }
    },
    /** Retry after failed / timeout: same path as install. */
    async retry() { await controller.install() },
    /** One poll; returns the new state. Waiting phases time out after stallMs without progress. */
    async poll(): Promise<RecoveryState> {
      if (state.phase !== 'installing' && state.phase !== 'downloading') return state
      const report = await api.readiness().catch(() => null)
      const next = report ? await fromCheck(report.checks?.transcription) : state
      if ((next.phase === 'installing' || next.phase === 'downloading') && next.percent === state.percent && next.phase === state.phase
        && now() - progressAt >= stallMs) {
        set({ ...next, phase: 'timeout' })
        return state
      }
      const waited = state.phase === 'installing' || state.phase === 'downloading'
      set(next)
      if (waited && next.phase === 'ready' && options.onReady) options.onReady()  // #232: continue by itself
      return state
    },
  }
  return controller
}

export type RecoveryController = ReturnType<typeof createRecoveryController>
