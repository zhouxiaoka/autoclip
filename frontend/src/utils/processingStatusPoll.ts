export interface ProcessingStatusPayload {
  status?: string | null
  task_status?: string | null
  current_step?: number | null
  total_steps?: number | null
  step_name?: string | null
  progress?: number | null
  task_progress?: number | null
  error_message?: string | null
}

export type ProcessingPhase = 'processing' | 'completed' | 'error' | 'pending'

export interface ProcessingStatusView {
  status: ProcessingPhase
  current_step: number
  total_steps: number
  step_name: string
  progress: number
  error_message?: string
}

export type StatusPollErrorKind = 'not_found' | 'server' | 'timeout' | 'transient'

const COMPLETED = new Set(['completed', 'success'])
const FAILED = new Set(['error', 'failed', 'cancelled', 'canceled'])

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim().toLowerCase() : ''
}

export function normalizeProcessingPhase(data: ProcessingStatusPayload | null | undefined): ProcessingPhase | 'unknown' {
  const raw = text(data?.status) || text(data?.task_status)
  if (COMPLETED.has(raw)) return 'completed'
  if (FAILED.has(raw)) return 'error'
  if (raw === 'pending' || raw === 'waiting') return 'pending'
  if (raw === 'processing' || raw === 'running') return 'processing'
  return 'unknown'
}

export function toProcessingView(data: ProcessingStatusPayload): ProcessingStatusView {
  const phase = normalizeProcessingPhase(data)
  const progress = data.progress ?? data.task_progress ?? 0
  return {
    status: phase === 'unknown' ? 'pending' : phase,
    current_step: data.current_step ?? 0,
    total_steps: data.total_steps ?? 6,
    step_name: data.step_name || '',
    progress: Number.isFinite(progress) ? progress : 0,
    error_message: data.error_message || undefined,
  }
}

export function httpStatusOf(error: unknown): number | undefined {
  if (!error || typeof error !== 'object') return undefined
  const status = (error as { response?: { status?: unknown } }).response?.status
  return typeof status === 'number' ? status : undefined
}

export function classifyStatusPollError(error: unknown): StatusPollErrorKind {
  const http = httpStatusOf(error)
  if (http === 404) return 'not_found'
  if (typeof http === 'number' && http >= 500 && http < 600) return 'server'
  const code = error && typeof error === 'object' ? (error as { code?: unknown }).code : undefined
  if (code === 'ECONNABORTED') return 'timeout'
  return 'transient'
}

/** Terminal pipeline state or HTTP failure. Timeouts stay in the retry bucket. */
export function shouldStopProcessingPoll(input: {
  phase?: ProcessingPhase | 'unknown'
  httpStatus?: number
  error?: unknown
}): boolean {
  if (input.phase === 'completed' || input.phase === 'error') return true
  if (input.error !== undefined) {
    const kind = classifyStatusPollError(input.error)
    return kind === 'not_found' || kind === 'server'
  }
  if (input.httpStatus === 404) return true
  return typeof input.httpStatus === 'number' && input.httpStatus >= 500 && input.httpStatus < 600
}
