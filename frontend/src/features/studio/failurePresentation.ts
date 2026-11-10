import { ADD_PROVIDER_HINT, QUOTA_RETRY_CHECK_BALANCE, SETTINGS_DESTINATION, TRANSCRIPTION_SETTINGS_DESTINATION, failureStep, pageFailureText, settingsDestination, type FailureStep, type PageFailureInfo } from './failureAction'
import { WHISPER_GATE_CODES } from './failureAction'
import { INSTALL_TRANSCRIPTION_LABEL } from './failureAction'
import { USER_MESSAGES } from '../../analytics/failureCodes'
import { ingestConnectionCopy } from '../../utils/llmFailure'
import { readableFailure } from './failureAction'
import { weakLocalTimelineFailure } from '../../utils/timelineFailure'

/** Sentence written for JobDurationExceeded. Old rows keep error_code timeout; only this exact sentence counts. */
export const JOB_BUDGET_REASON = '这次制作已超过时间上限，已停止。请重试；服务商一直很慢时可以换一个更快的模型。'
export const JOB_BUDGET_CODE = 'job_budget'
export const FAILURE_STATUS = '这次制作未完成'
export const NO_RESULT_OUTCOME = '本次没有可用成果'
export const KEPT_RESULT_OUTCOME = '已保留 {{count}} 条成片'
export const TECHNICAL_COUNT = '这次记录了 {{requests}} 次模型请求，其中 {{successes}} 次返回成功。这不是费用。'

const PLACEHOLDER_CODES = new Set(['validation', 'multiple', 'unknown', ''])
const EMPTY_VARIANT = '没有自动生成的成片，可选择备选片段继续生成'
const SOURCE_CODES = new Set(['source_unreadable', 'source_too_short', 'source_no_audio', 'source_not_found', 'source_unsupported', 'file_locked'])

export type PrimaryKind = 'retry' | 'retry_production' | 'view_results' | 'settings' | 'install_transcription' | 'change_video' | 'browser' | 'switch_model' | 'quota_check'

export type PrimaryAction = {
  id: PrimaryKind
  label: string
  destination?: string
}

export type FailureView = {
  status: string
  step: FailureStep | null
  reason: string
  outcome: string
  primary: PrimaryAction | null
  technical: { requests: number | null; successes: number | null } | null
}

export type PresentInput = {
  error?: string | null
  error_code?: string | null
  upstream_error_type?: string | null
  failure_stage?: string | null
  phase?: string | null
  preservedCount?: number | null
  connectionCount?: number | null
  llm_calls?: number | null
  billable_calls_before_failure?: number | null
  quotaUnlocked?: boolean
  secondary_error_codes?: readonly string[] | null
  secondary_upstream_error_types?: readonly string[] | null
  secondary_failure_stages?: readonly string[] | null
}

type CauseRecord = {
  error?: string | null
  error_code?: string | null
  failure_stage?: string | null
  upstream_error_type?: string | null
  phase?: string | null
  llm_calls?: number | null
  billable_calls_before_failure?: number | null
  secondary_error_codes?: readonly string[] | null
  secondary_upstream_error_types?: readonly string[] | null
  secondary_failure_stages?: readonly string[] | null
}

export function isKnownBudgetFailure(code?: string | null, error?: string | null): boolean {
  if (code === JOB_BUDGET_CODE) return true
  const text = (error || '').trim()
  if (!text) return false
  if (text === JOB_BUDGET_REASON) return true
  const marked = `：${JOB_BUDGET_REASON}`
  return text.endsWith(marked) && text.length <= JOB_BUDGET_REASON.length + 16
}

function specific(record?: CauseRecord | null): boolean {
  if (!record) return false
  const code = record.error_code || ''
  if (!code || PLACEHOLDER_CODES.has(code)) return false
  if ((record.error || '') === EMPTY_VARIANT) return false
  return true
}

/** Analysis wins when generation is only the empty-output placeholder. Receipt, when present, wins over both. */
export function resolveFailureCause(input: {
  analysis?: CauseRecord | null
  generation?: CauseRecord | null
  receipt?: CauseRecord | null
}): CauseRecord {
  const analysis = input.analysis || null
  const generation = input.generation || null
  const receipt = input.receipt || null
  let chosen: CauseRecord = {}
  if (specific(analysis) && !specific(generation)) chosen = { ...analysis }
  else if (specific(generation) && !specific(analysis)) chosen = { ...generation }
  else if (specific(analysis) && specific(generation) && analysis?.error_code !== generation?.error_code) chosen = { ...analysis }
  else if (generation?.error || generation?.error_code) chosen = { ...generation }
  else chosen = { ...(analysis || {}) }
  // The chosen record's own stage. Do not replace it with the other record's stage.
  if (receipt?.error_code) {
    chosen = {
      ...chosen,
      error_code: receipt.error_code,
      failure_stage: receipt.failure_stage || chosen.failure_stage,
      upstream_error_type: receipt.upstream_error_type || chosen.upstream_error_type,
      secondary_error_codes: receipt.secondary_error_codes,
      secondary_upstream_error_types: receipt.secondary_upstream_error_types,
      secondary_failure_stages: receipt.secondary_failure_stages,
    }
  }
  if (!chosen.phase && analysis?.phase) chosen = { ...chosen, phase: analysis.phase }
  const requests = [analysis?.llm_calls, generation?.llm_calls].map(value => Number(value)).filter(value => Number.isFinite(value) && value > 0)
  const successes = [analysis?.billable_calls_before_failure, generation?.billable_calls_before_failure].map(value => Number(value)).filter(value => Number.isFinite(value) && value >= 0)
  if (requests.length) chosen.llm_calls = Math.max(...requests)
  if (successes.length) chosen.billable_calls_before_failure = Math.max(...successes)
  return chosen
}

function fixableSecondary(input: PresentInput): PrimaryAction | null {
  const codes = input.secondary_error_codes || []
  const upstreams = input.secondary_upstream_error_types || []
  const stages = input.secondary_failure_stages || []
  for (let i = 0; i < codes.length; i += 1) {
    const code = codes[i] || ''
    const upstream = upstreams[i] || ''
    const stage = stages[i] || input.failure_stage
    if (upstream === 'insufficient_quota' || code === 'insufficient_quota') {
      return { id: 'quota_check', label: QUOTA_RETRY_CHECK_BALANCE, destination: settingsDestination(stage) }
    }
    if (code === 'authentication' || code === 'invalid_key' || code === 'llm_auth_invalid' || code === 'llm_not_configured' || code === 'permission_denied' || upstream === 'invalid_key' || upstream === 'permission_denied') {
      return { id: 'settings', label: '去设置', destination: settingsDestination(stage) }
    }
  }
  return null
}

function reasonFor(input: PresentInput): string {
  if (weakLocalTimelineFailure(input.error, input.error_code)) return '当前本地模型无法返回可用时间线'
  if (isKnownBudgetFailure(input.error_code, input.error)) return JOB_BUDGET_REASON
  const ingest = ingestConnectionCopy(input.error_code, input.upstream_error_type, input.failure_stage)
  if (ingest) return ingest
  const text = pageFailureText({
    error: input.error,
    error_code: input.error_code,
    upstream_error_type: input.upstream_error_type,
    failure_stage: input.failure_stage,
  }).trim()
  if (!text || text === '错误' || text === '失败' || text === 'failure' || text === ADD_PROVIDER_HINT) {
    return readableFailure('', input.error_code, input.upstream_error_type)
  }
  const catalog = input.error_code ? USER_MESSAGES[input.error_code] : ''
  if (catalog && !/[\u4e00-\u9fff]/.test(text)) return catalog
  return text
}

function primaryFor(input: PresentInput, preserved: number): PrimaryAction | null {
  if (preserved > 0) return { id: 'view_results', label: '查看已有结果' }
  if (weakLocalTimelineFailure(input.error, input.error_code)) {
    return { id: 'settings', label: '去配置模型', destination: '/settings?section=analysis' }
  }
  const code = input.error_code || ''
  const upstream = input.upstream_error_type || ''
  if (isKnownBudgetFailure(code, input.error)) return { id: 'retry_production', label: '重试制作' }
  if (code === 'whisper_installing') {
    return { id: 'install_transcription', label: '打开转写设置', destination: TRANSCRIPTION_SETTINGS_DESTINATION }
  }
  if ((WHISPER_GATE_CODES as readonly string[]).includes(code)) {
    return { id: 'install_transcription', label: INSTALL_TRANSCRIPTION_LABEL, destination: TRANSCRIPTION_SETTINGS_DESTINATION }
  }
  if (code === 'source_blocked') return { id: 'browser', label: '选择已登录的浏览器' }
  if (SOURCE_CODES.has(code)) return { id: 'change_video', label: '换一个视频' }
  if (upstream === 'insufficient_quota' || code === 'insufficient_quota') {
    return { id: 'quota_check', label: QUOTA_RETRY_CHECK_BALANCE, destination: settingsDestination(input.failure_stage) }
  }
  if (code === 'llm_not_configured' || code === 'llm_auth_invalid' || code === 'invalid_key' || code === 'authentication' || upstream === 'invalid_key' || upstream === 'permission_denied') {
    return { id: 'settings', label: '去设置', destination: settingsDestination(input.failure_stage) }
  }
  const connections = Number(input.connectionCount)
  const several = Number.isFinite(connections) && connections >= 2
  const secondaryFix = fixableSecondary(input)
  if (!isKnownBudgetFailure(code, input.error) && (code === 'timeout' || upstream === 'timeout' || code === 'rate_limited' || upstream === 'rate_limited' || code === 'model_not_found' || upstream === 'model_not_found')) {
    if (secondaryFix) return secondaryFix
    if (several) return { id: 'switch_model', label: '换模型重试' }
    return { id: 'retry', label: '重试' }
  }
  if (code === 'connection' && (input.failure_stage === 'ingest' || input.failure_stage === 'download')) {
    return { id: 'retry', label: '重试' }
  }
  if (code === 'service_restarted' || code === 'unexpected' || code === 'timeline_empty' || code === 'transcription_empty') {
    return { id: 'retry_production', label: '重试制作' }
  }
  if (code === 'connection' && several) return { id: 'switch_model', label: '换模型重试' }
  if (code) return { id: 'retry', label: '重试' }
  return { id: 'retry', label: '重试' }
}

export function presentFailure(input: PresentInput): FailureView {
  const preserved = Math.max(0, Number(input.preservedCount) || 0)
  const requests = Number(input.llm_calls)
  const successes = Number(input.billable_calls_before_failure)
  return {
    status: SOURCE_CODES.has(input.error_code || '') || input.error_code === 'source_blocked' ? '这个素材无法使用' : FAILURE_STATUS,
    step: failureStep(input.failure_stage, input.phase, input.error_code),
    reason: reasonFor(input),
    outcome: preserved > 0 ? KEPT_RESULT_OUTCOME : NO_RESULT_OUTCOME,
    primary: primaryFor(input, preserved),
    technical: Number.isFinite(requests) && requests > 0 ? { requests, successes: Number.isFinite(successes) ? successes : null } : null,
  }
}

/** Drafts, finished variants, clips, collections, and completed exports not already represented by a variant. */
export function countPreservedResults(input: {
  drafts?: number | null
  completedVariants?: number | null
  clips?: number | null
  collections?: number | null
  completedJobs?: number | null
}): number {
  return [input.drafts, input.completedVariants, input.clips, input.collections, input.completedJobs]
    .reduce<number>((sum, value) => sum + Math.max(0, Number(value) || 0), 0)
}

export function technicalCountText(view: FailureView): string | null {
  if (!view.technical || view.technical.requests == null || view.technical.successes == null) return null
  return TECHNICAL_COUNT
}

export type { PageFailureInfo, FailureStep }
export { SETTINGS_DESTINATION }
