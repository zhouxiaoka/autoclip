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
export type TranscriptionRoute = 'platform_subs' | 'whisper' | 'cloud' | 'srt'

export interface SubmissionOptions {
  source?: 'link' | 'file'
  /** Link imports can use captions the platform already published. Files still need a transcriber or an SRT. */
  allowLinkWithoutWhisper?: boolean
}

const ORDER = ['analysis', 'transcription', 'visual', 'ffmpeg'] as const

/** Gate the import button. An attached SRT covers a missing transcriber. A failed probe does not trap the user. */
export function submissionBlock(report: ImportReadiness | null, hasSubtitle: boolean, settled: boolean, options: SubmissionOptions = {}): BlockReason | null {
  if (!settled) return 'pending'
  if (!report) return null
  if (!report.checks.analysis.ok) return 'analysis'
  if (!report.checks.transcription.ok && !hasSubtitle && !(options.allowLinkWithoutWhisper && options.source !== 'file')) return 'transcription'
  if (!report.checks.visual.ok) return 'visual'
  if (!report.checks.ffmpeg.ok) return 'ffmpeg'
  return null
}

export function visibleIssues(report: ImportReadiness | null, hasSubtitle: boolean, options: SubmissionOptions = {}): ReadinessIssue[] {
  if (!report) return []
  const skipTranscription = options.allowLinkWithoutWhisper && options.source !== 'file'
  return ORDER.flatMap(key => {
    const check = report.checks[key]
    if (check.ok || (key === 'transcription' && (hasSubtitle || skipTranscription))) return []
    return [{ key, ...check }]
  })
}

/** Enum only. A link that skipped the local transcriber is reported as platform captions, which is what the backend tries first. */
export function transcriptionRoute(input: { hasSubtitle: boolean; code?: string; skippedWhisper: boolean }): TranscriptionRoute {
  if (input.hasSubtitle) return 'srt'
  if (input.skippedWhisper) return 'platform_subs'
  if (input.code === 'cloud_configured') return 'cloud'
  return 'whisper'
}

export function repairDestination(repair: RepairAction): string | null {
  if (repair === 'settings_ai') return '/settings?section=ai'
  if (repair === 'settings_transcription') return '/settings?section=speech'
  if (repair === 'settings_vision') return '/settings?section=vision'
  return null
}
