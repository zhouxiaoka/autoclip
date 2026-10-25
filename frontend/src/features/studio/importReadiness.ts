export type RepairAction = 'settings_ai' | 'install_whisper' | 'settings_transcription' | 'settings_vision' | 'none'
export type AnalysisMode = 'auto' | 'subtitle' | 'visual'

export interface ReadinessCheck {
  ok: boolean
  code: string
  repair: RepairAction
  /** whisper_model_* checks name the model the import needs. */
  model?: string
  /** Transcription only: the backend says this setup may run without ASR (visual route); its import gate decides per file. */
  skippable?: boolean
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
  // (PM): submit re-probes up to READINESS_RETRIES times first; still null -> let the backend gate decide (422).
  if (!report) return null
  // A missing check is unknown, not failed: it never traps the user (same as a failed probe).
  const checks = report.checks
  if (checks?.analysis?.ok === false) return 'analysis'
  if (checks?.transcription?.ok === false && !hasSubtitle && !(options.allowLinkWithoutWhisper && options.source !== 'file') && !checks.transcription.skippable) return 'transcription'
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

/** One mapping from a transcription check code (readiness report or coded backend 422) to the prompt.*/
export function gateKind(code: string | undefined): 'install' | 'installing' | null {
  if (code === 'whisper_installing' || code === 'whisper_model_downloading') return 'installing'
  return code === 'whisper_not_installed' || code === 'whisper_install_failed' || code === 'whisper_model_missing' || code === 'whisper_model_failed' ? 'install' : null
}

/** failures of the source itself (user cause, excluded from the success rate); retrying cannot help.*/
export const SOURCE_FAILURE_CODES = ['source_unreadable', 'source_too_short', 'source_no_audio', 'source_not_found'] as const
export function sourceFailure(code: string | null | undefined): boolean {
  return !!code && (SOURCE_FAILURE_CODES as readonly string[]).includes(code)
}

/** the settings entry a failed run offers, by error code. A Whisper gate code opens transcription
 * settings (where the one-click install lives); everything else keeps the model settings entry. */
export function failureSettings(code: string | null | undefined): { label: string; to: string } {
  // a source the pipeline cannot use is fixed by another file, not by settings or a retry.
  if (sourceFailure(code)) return { label: '换一个视频', to: '/' }
  return gateKind(code || undefined)
    ? { label: '打开转写设置', to: repairDestination('settings_transcription') as string }
    : { label: '模型设置', to: repairDestination('settings_ai') as string }
}

export const CLOUD_TRANSCRIPTION_DESTINATION = '/settings?section=speech&provider=cloud'

/** how many times submit re-runs a failed readiness probe before handing the decision to the backend.*/
export const READINESS_RETRIES = 3

export async function probeReadiness(load: () => Promise<ImportReadiness | null>, retries = READINESS_RETRIES): Promise<ImportReadiness | null> {
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const value = await load()
      if (value) return value
    } catch { /* retry */ }
  }
  return null
}
