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
  // A missing check is unknown, not failed: it never traps the user (same as a failed probe).
  const checks = report.checks
  if (checks?.analysis?.ok === false) return 'analysis'
  if (checks?.transcription?.ok === false && !hasSubtitle && !(options.allowLinkWithoutWhisper && options.source !== 'file')) return 'transcription'
  if (checks?.visual?.ok === false) return 'visual'
  if (checks?.ffmpeg?.ok === false) return 'ffmpeg'
  return null
}

export function visibleIssues(report: ImportReadiness | null, hasSubtitle: boolean, options: SubmissionOptions = {}): ReadinessIssue[] {
  if (!report) return []
  const skipTranscription = options.allowLinkWithoutWhisper && options.source !== 'file'
  return ORDER.flatMap(key => {
    const check = report.checks?.[key]
    if (!check || check.ok || (key === 'transcription' && (hasSubtitle || skipTranscription))) return []
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

/** Allowlisted ASR probe payload. Never reads model names or paths. */
export function asrReadinessProperties(report: ImportReadiness | null, hasSubtitle: boolean): Record<string, unknown> {
  const checks = report && report.checks
  const transcription = checks && checks.transcription
  const code = transcription && typeof transcription.code === 'string' ? transcription.code : undefined
  let provider = 'whisper_local'
  if (typeof code === 'string' && code.indexOf('sensevoice') === 0) provider = 'sensevoice_local'
  else if (typeof code === 'string' && code.indexOf('cloud') === 0) provider = 'cloud'
  const blocked = Boolean(transcription && transcription.ok === false && !hasSubtitle)
  return { provider, code, has_subtitle: hasSubtitle, blocked }
}

/** 1.5.8: local file, local Whisper selected but not installed, no SRT -> blocking install prompt.
 * Offers the existing install flow or an explicit switch to cloud; never switches automatically. */
export function localTranscriptionGate(report: ImportReadiness | null, hasSubtitle: boolean, source: SubmissionOptions['source']): 'install' | 'installing' | null {
  if (hasSubtitle || source !== 'file') return null
  if (report?.analysis_mode === 'visual') return null
  const code = report?.checks?.transcription?.code
  if (code === 'whisper_installing') return 'installing'
  return code === 'whisper_not_installed' || code === 'whisper_install_failed' ? 'install' : null
}

export const CLOUD_TRANSCRIPTION_DESTINATION = '/settings?section=speech&provider=cloud'
