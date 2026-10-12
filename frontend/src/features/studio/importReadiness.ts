export type RepairAction = 'settings_ai' | 'install_whisper' | 'settings_transcription' | 'settings_vision' | 'none'
export type AnalysisMode = 'auto' | 'subtitle' | 'visual'

export interface ReadinessCheck {
  ok: boolean
  code: string
  repair: RepairAction
  /** whisper_model_* checks name the model the import needs. */
  model?: string
}

export interface ImportReadiness {
  analysis_mode: AnalysisMode
  ready: boolean
  /** Older or partial backends may omit the object or single checks (AUTOCLIP-FRONTEND-C). */
  checks?: {
    analysis?: ReadinessCheck | null
    transcription?: ReadinessCheck | null
    visual?: ReadinessCheck | null
    ffmpeg?: ReadinessCheck | null
  } | null
}

export interface ReadinessIssue extends ReadinessCheck {
  key: 'analysis' | 'transcription' | 'visual' | 'ffmpeg'
}

export type BlockReason = 'pending' | 'analysis' | 'transcription' | 'visual' | 'ffmpeg'

const ORDER = ['analysis', 'transcription', 'visual', 'ffmpeg'] as const

/** Gate the import button. An attached SRT covers a missing transcriber. A failed probe does not trap the user. */
export function submissionBlock(report: ImportReadiness | null, hasSubtitle: boolean, settled: boolean): BlockReason | null {
  if (!settled) return 'pending'
  if (!report) return null
  // A missing check is unknown, not failed: it never traps the user (same as a failed probe).
  const checks = report.checks
  if (checks?.analysis?.ok === false) return 'analysis'
  if (checks?.transcription?.ok === false && !hasSubtitle) return 'transcription'
  if (checks?.visual?.ok === false) return 'visual'
  if (checks?.ffmpeg?.ok === false) return 'ffmpeg'
  return null
}

export function visibleIssues(report: ImportReadiness | null, hasSubtitle: boolean): ReadinessIssue[] {
  if (!report) return []
  return ORDER.flatMap(key => {
    const check = report.checks?.[key]
    if (!check || check.ok || (key === 'transcription' && hasSubtitle)) return []
    return [{ key, ...check }]
  })
}

export function repairDestination(repair: RepairAction): string | null {
  if (repair === 'settings_ai') return '/settings?section=ai'
  if (repair === 'settings_transcription') return '/settings?section=speech'
  if (repair === 'settings_vision') return '/settings?section=vision'
  return null
}
