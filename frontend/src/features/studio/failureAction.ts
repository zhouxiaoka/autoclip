import { USER_CAUSE_ERROR_CODES, USER_CAUSE_UPSTREAM_TYPES, USER_MESSAGES } from '../../analytics/failureCodes'
import { USER_CAUSE_REASONS, llmFailureText } from '../../utils/llmFailure'
/**
 * 1.5.7 failed-state action. User-attributable causes (bad/expired key, no balance, no model
 * configured, key lacks permission) cannot be fixed by retrying: show 「去设置」 instead.
 * Mirrors event_catalog.json attribution.user_cause (contract-tested; same set the v4
 * success rate excludes as user cause).
 */
export { USER_CAUSE_ERROR_CODES, USER_CAUSE_UPSTREAM_TYPES }

export const SETTINGS_DESTINATION = '/settings?section=analysis'
/** Cloud transcription (ASR) credentials. SettingsPage maps `speech` to the transcription row;
 * `section=transcription` is not a recognised value there (falls back to the top of AI settings). */
export const TRANSCRIPTION_SETTINGS_DESTINATION = '/settings?section=speech'


export type FailureAction = { kind: 'retry' } | { kind: 'settings'; reason: string; destination: string }

/** Which settings row fixes a user-cause failure, keyed by failure_stage (one table):
 * subtitle = cloud transcription (ASR), vision = visual-understanding binding; everything else
 * is the text-analysis binding. Values are SettingsPage SECTION_ALIASES keys. */
const STAGE_SECTION: Record<string, string> = { subtitle: 'speech', vision: 'vision' }
export const VISION_SETTINGS_DESTINATION = '/settings?section=vision'

export function settingsDestination(failureStage?: string | null): string {
  const section = STAGE_SECTION[failureStage || '']
  return section ? `/settings?section=${section}` : SETTINGS_DESTINATION
}

const isIn = (list: readonly string[], value?: string | null): value is string => !!value && list.includes(value)

/** One classification: the controlled upstream type is the most precise signal and wins; the
 * coarse error_code is only used when upstream says nothing user-attributable. */
export function failureAction(errorCode?: string | null, upstreamType?: string | null, failureStage?: string | null): FailureAction {
  const code = isIn(USER_CAUSE_UPSTREAM_TYPES, upstreamType) ? upstreamType
    : isIn(USER_CAUSE_ERROR_CODES, errorCode) || isIn(USER_CAUSE_UPSTREAM_TYPES, errorCode) ? errorCode : ''
  return code ? { kind: 'settings', reason: USER_CAUSE_REASONS[code], destination: settingsDestination(failureStage) } : { kind: 'retry' }
}

export type PageFailureInfo = {
  error_code?: string | null; upstream_error_type?: string | null; failure_stage?: string | null
  phase?: string | null
  billable_calls_before_failure?: number | null
  secondary_error_codes?: readonly string[] | null; secondary_upstream_error_types?: readonly string[] | null; secondary_failure_stages?: readonly string[] | null
}

/** Fixed sentence. No amount, no invoice. Shown only after a billable call already happened. */
export const BILLING_GUIDANCE = '这次请求可能已经由服务商计费。重试前请先核对余额，并在设置里测试连接。'

const BARE_FAILURE = new Set(['', '错误', '失败', 'Error', 'error', '处理失败', '处理失败：错误'])
const DOWNLOAD_CODES = new Set(['source_unreadable', 'source_too_short', 'source_no_audio', 'source_not_found', 'source_blocked', 'file_locked'])
const TRANSCRIBE_STAGES = new Set(['subtitle', 'transcribe'])
const ANALYZE_STAGES = new Set(['analyze', 'outline', 'timeline', 'scoring', 'title', 'clustering', 'vision', 'highlight'])

/** The four steps a beginner can act on: download / transcribe / analyze / produce. */
export function failureStep(stage?: string | null, phase?: string | null, code?: string | null): '下载' | '转写' | '分析' | '制作' {
  if (code && (DOWNLOAD_CODES.has(code) || code.startsWith('whisper_') || code === 'transcription_empty' || code === 'subtitle_setup')) {
    return code.startsWith('whisper_') || code === 'transcription_empty' || code === 'subtitle_setup' ? '转写' : '下载'
  }
  const key = (stage || '').toLowerCase()
  if (TRANSCRIBE_STAGES.has(key)) return '转写'
  if (ANALYZE_STAGES.has(key)) return '分析'
  if (key === 'render' || key === 'export' || phase === 'rendering') return '制作'
  if (key === 'ingest' || key === 'screening') return '下载'
  // Screening without a model code is still the download/read step. Production is analysis
  // until rendering starts. A model failure during screening names the analysis step.
  if (phase === 'screening') return code ? '分析' : '下载'
  if (phase === 'production') return '分析'
  return '制作'
}

export function readableFailure(error?: string | null, code?: string | null, upstream?: string | null): string {
  const text = llmFailureText(error, code, upstream).trim()
  if (!BARE_FAILURE.has(text)) return text
  if (upstream && upstream !== 'unknown' && USER_MESSAGES[upstream]) return USER_MESSAGES[upstream]
  if (code && USER_MESSAGES[code]) return USER_MESSAGES[code]
  return USER_MESSAGES.unknown
}

export function presentedFailure(info: PageFailureInfo & { error?: string | null }, message?: string | null): { step: '下载' | '转写' | '分析' | '制作'; reason: string; billing: string | null } {
  const raw = (message ?? readableFailure(info.error, info.error_code, info.upstream_error_type)).trim()
  const reason = BARE_FAILURE.has(raw) ? readableFailure(info.error, info.error_code, info.upstream_error_type) : raw
  const count = Number(info.billable_calls_before_failure)
  return {
    step: failureStep(info.failure_stage, info.phase, info.error_code),
    reason: BARE_FAILURE.has(reason) ? USER_MESSAGES.unknown : reason,
    billing: Number.isFinite(count) && count > 0 ? BILLING_GUIDANCE : null,
  }
}

/** Page fallback when the run has no attempt receipt: the analysis record's own cause fields. */
export function analysisPageFailure(
  analysis?: { error_code?: string; upstream_error_type?: string; failure_stage?: string } | null,
  generation?: { error_code?: string } | null,
): PageFailureInfo {
  return {
    error_code: analysis?.error_code || generation?.error_code,
    upstream_error_type: analysis?.upstream_error_type,
    failure_stage: analysis?.failure_stage,
    ...pickSecondary(analysis),
  }
}

/** User sentence for a settled page cause. The fine upstream type stays inside this reader. */
export function pageFailureText(info: { error?: string | null; error_code?: string | null; upstream_error_type?: string | null }): string {
  return llmFailureText(info.error, info.error_code, info.upstream_error_type)
}

export function analysisFailureText(
  error: string | null | undefined,
  analysis?: { error_code?: string; upstream_error_type?: string; failure_stage?: string } | null,
  generation?: { error_code?: string } | null,
): string {
  return pageFailureText({ error, ...analysisPageFailure(analysis, generation) })
}

/** (PM rule): page hint and stats are separate. Stats keep the product-first primary cause
 * (backend failure_attribution); the page leads with the first cause the user can fix (e.g. auth),
 * because retrying cannot fix it. Primary first, then secondaries in recorded order. */
export function pageFailureAction(info: PageFailureInfo): FailureAction {
  const primary = failureAction(info.error_code, info.upstream_error_type, info.failure_stage)
  if (primary.kind === 'settings') return primary
  const codes = info.secondary_error_codes || []
  for (let i = 0; i < codes.length; i++) {
    const action = failureAction(codes[i], info.secondary_upstream_error_types?.[i], info.secondary_failure_stages?.[i])
    if (action.kind === 'settings') return action
  }
  return primary
}

const strings = (v: unknown) => Array.isArray(v) ? v.map(x => typeof x === 'string' ? x : '') : undefined
/** The secondary causes of an analysis record, for the page rule. */
export function pickSecondary(analysis: unknown): Pick<PageFailureInfo, 'secondary_error_codes' | 'secondary_upstream_error_types' | 'secondary_failure_stages'> {
  const a = (analysis || {}) as Record<string, unknown>
  return { secondary_error_codes: strings(a.secondary_error_codes), secondary_upstream_error_types: strings(a.secondary_upstream_error_types), secondary_failure_stages: strings(a.secondary_failure_stages) }
}

type Receipt = { sequence?: number; state?: string; run_id?: string | null; causes?: { stage?: string; code?: string; upstream?: string }[] }
/** #419: the page reads the settled backend attempt receipt of the failed run it shows (its structured causes,
 * primary first). A failure outside any attempt (e.g. screening) has no receipt: null, the caller uses analysis. */
export function receiptFailureInfo(attempts: readonly Receipt[] | null | undefined, runId?: string | null): PageFailureInfo | null {
  const settled = (attempts || []).filter(a => ['completed', 'partial', 'failed'].includes(a.state || ''))
  const latest = settled.reduce<Receipt | null>((best, a) => !best || (a.sequence || 0) > (best.sequence || 0) ? a : best, null)
  if (!latest || !runId || latest.run_id !== runId || latest.state === 'completed' || !latest.causes?.length) return null
  const [primary, ...rest] = latest.causes
  return { error_code: primary.code, upstream_error_type: primary.upstream || null, failure_stage: primary.stage || null,
    secondary_error_codes: rest.map(c => c.code || ''), secondary_upstream_error_types: rest.map(c => c.upstream || ''), secondary_failure_stages: rest.map(c => c.stage || '') }
}
