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
  /** One short sentence for the project card. The full reason stays on the diagnose panel. */
  brief: string
  briefValues?: { candidates: string; seconds: string }
  outcome: string
  primary: PrimaryAction | null
  recovery: PrimaryAction
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

const CARD_BRIEFS = {
  timeout: '响应超时了，可以重试。',
  job_budget: '制作时间太长，已经停止。',
  connection: '网络中断了，可以重试。',
  download: '下载时网络中断了。',
  service_restarted: '应用刚重启，这次制作中断了。',
  insufficient_quota: '额度用完了，请检查余额。',
  rate_limited: '请求太频繁，请稍后再试。',
  auth: '密钥或权限有问题，请到设置里检查。',
  llm_not_configured: '还没有配好模型，请到设置里检查。',
  duration: '{{candidates}} 个候选片段都不足 {{seconds}} 秒。请换用口播连续、话题完整的素材。',
  interrupted: '制作中断了，可以重试。',
  timeline: '当前模型没能排出时间线。',
  unknown: '这次没有做完，可以重试。',
} as const

const AUTH_CODES = new Set(['authentication', 'invalid_key', 'llm_auth_invalid', 'permission_denied'])
// Only interpolate the two numbers emitted by timeline_failure_from_report.
const MINIMUM_DURATION = /时间线提取为空：([0-9]+) 个有效候选在字幕边界校正后均未达到最短时长（([0-9]+(?:\.[0-9]+)?) 秒）/
const MODEL_FILE_MISSING = '转写模型文件缺失或不完整，请重新下载。'

/** Card sentence. A long vendor message never becomes the card text, even when it has no line break. */
export function briefReason(input: PresentInput): string {
  if (weakLocalTimelineFailure(input.error, input.error_code)) return CARD_BRIEFS.timeline
  if (isKnownBudgetFailure(input.error_code, input.error)) return CARD_BRIEFS.job_budget
  const code = input.error_code || ''
  const upstream = input.upstream_error_type || ''
  const stage = input.failure_stage || ''
  if ((code === 'connection' || upstream === 'connection' || upstream === 'timeout' || code === 'timeout') && (stage === 'ingest' || stage === 'download')) {
    return CARD_BRIEFS.download
  }
  if (code === 'insufficient_quota' || upstream === 'insufficient_quota') return CARD_BRIEFS.insufficient_quota
  if (AUTH_CODES.has(code) || AUTH_CODES.has(upstream) || upstream === 'invalid_key') return CARD_BRIEFS.auth
  if (code === 'llm_not_configured') return CARD_BRIEFS.llm_not_configured
  if (code === 'timeout' || upstream === 'timeout') return CARD_BRIEFS.timeout
  if (code === 'connection' || upstream === 'connection') return CARD_BRIEFS.connection
  if (code === 'service_restarted' || upstream === 'service_restarted') return CARD_BRIEFS.service_restarted
  if (code === 'rate_limited' || upstream === 'rate_limited') return CARD_BRIEFS.rate_limited
  if (code === 'whisper_model_missing' || code === 'whisper_model_failed'
      || (!code && input.error === 'Whisper 模型文件缺失或不完整。')) return MODEL_FILE_MISSING
  if (upstream && upstream !== 'unknown' && USER_MESSAGES[upstream]) return USER_MESSAGES[upstream]
  if (code === 'unexpected') return CARD_BRIEFS.interrupted
  if (code && code !== 'unknown' && USER_MESSAGES[code]) return USER_MESSAGES[code]
  const stored = input.error?.trim()
  return stored && Object.values(USER_MESSAGES).includes(stored) ? stored : CARD_BRIEFS.unknown
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

function primaryFor(input: PresentInput): PrimaryAction {
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
  if (code === 'llm_not_configured' || code === 'llm_auth_invalid' || code === 'invalid_key' || code === 'authentication' || code === 'bad_endpoint' || upstream === 'invalid_key' || upstream === 'permission_denied' || upstream === 'bad_endpoint') {
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
  const recovery = primaryFor(input)
  const requests = Number(input.llm_calls)
  const successes = Number(input.billable_calls_before_failure)
  const duration = (!input.error_code || ['timeline_empty', 'unexpected', 'unknown'].includes(input.error_code))
    ? MINIMUM_DURATION.exec(input.error || '') : null
  return {
    status: SOURCE_CODES.has(input.error_code || '') || input.error_code === 'source_blocked' ? '这个素材无法使用' : FAILURE_STATUS,
    step: failureStep(input.failure_stage, input.phase, input.error_code),
    reason: reasonFor(input),
    brief: duration ? CARD_BRIEFS.duration : briefReason(input),
    ...(duration && { briefValues: { candidates: duration[1], seconds: duration[2] } }),
    outcome: preserved > 0 ? KEPT_RESULT_OUTCOME : NO_RESULT_OUTCOME,
    primary: preserved > 0 ? { id: 'view_results', label: '查看已有结果' } : recovery,
    recovery,
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
