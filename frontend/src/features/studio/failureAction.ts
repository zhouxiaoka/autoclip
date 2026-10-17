import { USER_CAUSE_REASONS } from '../../utils/llmFailure'
/**
 * 1.5.8 failed-state action. User-attributable causes (bad/expired key, no balance, no model
 * configured, key lacks permission) cannot be fixed by retrying: show 「去设置」 instead.
 * Mirrors event_catalog.json attribution.user_cause (contract-tested; same set the v4
 * success rate excludes as user cause).
 */
export const USER_CAUSE_ERROR_CODES = ['authentication', 'llm_auth_invalid', 'invalid_key', 'insufficient_quota', 'llm_not_configured'] as const
export const USER_CAUSE_UPSTREAM_TYPES = ['invalid_key', 'insufficient_quota', 'permission_denied'] as const

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
  secondary_error_codes?: readonly string[] | null; secondary_upstream_error_types?: readonly string[] | null; secondary_failure_stages?: readonly string[] | null
}

/** R24 (PM rule): page hint and stats are separate. Stats keep the product-first primary cause
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
