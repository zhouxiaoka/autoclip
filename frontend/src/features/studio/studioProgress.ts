/** Project-scale Studio bar. Weights match backend/services/simple_progress.py. */

const STAGES: readonly [string, number][] = [
  ['INGEST', 10],
  ['SUBTITLE', 15],
  ['ANALYZE', 20],
  ['HIGHLIGHT', 25],
  ['EXPORT', 20],
  ['DONE', 10],
]

const STAGE_LABEL: Record<string, string> = {
  INGEST: '素材准备',
  SUBTITLE: '字幕处理',
  ANALYZE: '内容分析',
  HIGHLIGHT: '片段定位',
  EXPORT: '视频导出',
  DONE: '处理完成',
}

const EASE_TAU_SEC = 90
const RUNNING_CAP = 95
const MODEL_BUDGET_STAGES = new Set(['ANALYZE', 'HIGHLIGHT'])

export function stageBand(stage: string): { start: number; end: number } {
  let done = 0
  for (const [name, weight] of STAGES) {
    if (name === stage) {
      if (name === 'DONE') return { start: 100, end: 100 }
      return { start: Math.min(99, done), end: Math.min(99, done + weight) }
    }
    done += weight
  }
  return { start: 0, end: 10 }
}

/** Ease `base` toward 90% of the stage band. Never 100, never past 95, never backward. */
export function easePercent(stage: string, base: number, elapsedSec: number): number {
  if (stage === 'DONE') return 100
  const { start, end } = stageBand(stage)
  if (end <= start) return clampRunning(base)
  let ceiling = start + Math.floor((end - start) * 0.9)
  if (ceiling >= end) ceiling = Math.max(start, end - 1)
  ceiling = Math.min(RUNNING_CAP, Math.max(start, ceiling))
  const floor = Math.max(start, Math.min(99, Math.round(base)))
  if (floor >= ceiling) return Math.min(99, floor)
  const moved = (ceiling - floor) * (1 - Math.exp(-Math.max(0, elapsedSec) / EASE_TAU_SEC))
  return Math.min(ceiling, floor + Math.floor(moved))
}

function clampRunning(value: number): number {
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(RUNNING_CAP, Math.round(value)))
}

export interface StudioProgressInput {
  analysis: {
    status?: string
    phase?: string
    message?: string
    percent?: number
    progress_percent?: number
    progress_stage?: string
    progress_approximate?: boolean
    progress_since?: number
    progress_message?: string
    created_at?: string
  } | null
  generation?: { created_at?: string } | null
  jobs?: { status: string; percent?: number }[]
}

export interface StudioProgressView {
  label: string
  percent: number
  approximate: boolean
  /** Whole minutes since the run started, or null when the start is unknown. */
  elapsedMinutes: number | null
  /** True only for model stages. Download, local transcription and export sit outside the 20-minute model cap. */
  modelBudget: boolean
  detail: string
}

function elapsedSeconds(iso: string | undefined, nowMs: number): number | null {
  if (!iso) return null
  const parsed = Date.parse(iso)
  if (!Number.isFinite(parsed)) return null
  return Math.max(0, (nowMs - parsed) / 1000)
}

function easeClock(since: number | undefined, nowMs: number): number {
  if (typeof since !== 'number' || since <= 0) return 0
  return Math.max(0, nowMs / 1000 - since)
}

function minutesOf(seconds: number | null): number | null {
  if (seconds == null) return null
  return Math.floor(seconds / 60)
}

export function studioRunProgress(input: StudioProgressInput, nowMs: number): StudioProgressView | null {
  const analysis = input.analysis
  const jobs = input.jobs || []
  const jobActive = jobs.some(job => job.status === 'running' || job.status === 'queued')
  if (!analysis || (analysis.status !== 'running' && !jobActive)) return null
  const phase = analysis.status === 'running' ? (analysis.phase || '') : 'rendering'
  const started = elapsedSeconds(input.generation?.created_at || analysis.created_at, nowMs)
  const elapsedMinutes = minutesOf(started)

  if (phase === 'rendering') {
    const active = jobs.filter(job => job.status === 'running' || job.status === 'queued')
    const measured = active.some(job => typeof job.percent === 'number' && job.percent > 0)
    const avg = active.length ? active.reduce((sum, job) => sum + (job.percent || 0), 0) / active.length : 0
    const { start, end } = stageBand('EXPORT')
    const mapped = start + Math.round((end - start) * Math.max(0, Math.min(100, avg)) / 100)
    const carried = typeof analysis.progress_percent === 'number' ? analysis.progress_percent : start
    const base = Math.max(start, carried, measured ? mapped : start)
    const clock = easeClock(analysis.progress_since, nowMs)
    const percent = clampRunning(measured ? base : Math.max(base, easePercent('EXPORT', base, clock)))
    return {
      label: STAGE_LABEL.EXPORT,
      percent,
      approximate: !measured,
      elapsedMinutes,
      modelBudget: false,
      detail: analysis.progress_message || analysis.message || '正在生成可发布成片',
    }
  }

  if (phase === 'screening') {
    const measured = typeof analysis.percent === 'number'
    const clock = easeClock(analysis.progress_since, nowMs)
    const percent = clampRunning(measured ? analysis.percent! : easePercent('INGEST', 0, clock))
    return {
      label: measured ? '下载中' : STAGE_LABEL.INGEST,
      percent,
      approximate: !measured,
      elapsedMinutes,
      modelBudget: false,
      detail: analysis.message || '',
    }
  }

  const transcribing = analysis.message === '正在生成字幕'
  const stage = analysis.progress_stage || (transcribing ? 'SUBTITLE' : 'ANALYZE')
  const band = stageBand(stage)
  let reported: number | null = typeof analysis.progress_percent === 'number' ? analysis.progress_percent : null
  if (reported == null && transcribing && typeof analysis.percent === 'number') {
    reported = band.start + Math.round((band.end - band.start) * Math.max(0, Math.min(100, analysis.percent)) / 100)
  }
  if (reported == null) reported = band.start
  const explicit = analysis.progress_approximate
  const approximate = explicit === true
    || (explicit == null && !(transcribing && typeof analysis.percent === 'number') && typeof analysis.progress_percent !== 'number')
  const clock = easeClock(analysis.progress_since, nowMs)
  const eased = approximate ? easePercent(stage, band.start, clock) : reported
  return {
    label: STAGE_LABEL[stage] || STAGE_LABEL.ANALYZE,
    percent: clampRunning(Math.max(reported, eased)),
    approximate,
    elapsedMinutes,
    modelBudget: MODEL_BUDGET_STAGES.has(stage),
    detail: analysis.progress_message || analysis.message || '',
  }
}
