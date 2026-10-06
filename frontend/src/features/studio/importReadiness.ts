export type RepairAction = 'settings_ai' | 'install_whisper' | 'settings_transcription' | 'settings_vision' | 'none'
export type AnalysisMode = 'auto' | 'subtitle' | 'visual'

export interface ReadinessCheck {
  ok: boolean
  code: string
  repair: RepairAction
}

export interface ImportReadiness {
  analysis_mode: AnalysisMode
  ready: boolean
  checks: {
    analysis: ReadinessCheck
    transcription: ReadinessCheck
    visual: ReadinessCheck
    ffmpeg: ReadinessCheck
  }
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
  if (!report.checks.analysis.ok) return 'analysis'
  if (!report.checks.transcription.ok && !hasSubtitle) return 'transcription'
  if (!report.checks.visual.ok) return 'visual'
  if (!report.checks.ffmpeg.ok) return 'ffmpeg'
  return null
}

export function visibleIssues(report: ImportReadiness | null, hasSubtitle: boolean): ReadinessIssue[] {
  if (!report) return []
  return ORDER.flatMap(key => {
    const check = report.checks[key]
    if (check.ok || (key === 'transcription' && hasSubtitle)) return []
    return [{ key, ...check }]
  })
}

export function repairDestination(repair: RepairAction): string | null {
  if (repair === 'settings_ai') return '/settings?section=ai'
  if (repair === 'settings_transcription') return '/settings?section=speech'
  if (repair === 'settings_vision') return '/settings?section=vision'
  return null
}
