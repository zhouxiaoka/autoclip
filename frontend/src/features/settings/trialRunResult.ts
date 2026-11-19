/** F2 trial-run result lines + estimate copy. Pure helpers for the connection card. */

export type TrialResultLike = {
  ok?: boolean
  success?: boolean
  probe_kind?: 'quick' | 'trial'
  trial_context_ok?: boolean | null
  trial_rate_limited?: boolean | null
  trial_json_ok?: boolean | null
  /** ok | format | no_answer | transport | context | rate. Empty when the trial did not classify an answer. */
  trial_answer?: '' | 'ok' | 'format' | 'no_answer' | 'transport' | 'context' | 'rate'
  trial_avg_ms?: number | null
  trial_estimate_requests?: number | null
  trial_estimate_minutes?: number | null
  trial_passed?: boolean | null
}

export type TrialLineTone = 'ok' | 'warn' | 'fail'

export type TrialLine = {
  key: 'context' | 'rate' | 'json'
  tone: TrialLineTone
  /** Chinese source string used as i18n key. */
  label: string
}

const TIMEOUT_LINE = '模型响应超时，请检查服务和网络后重试；本地模型请确认服务仍在运行。'
const NO_ANSWER_LINE = '模型只返回了思考过程，没有最终回答。请换一个会直接作答的模型。'

export function trialLines(result: TrialResultLike | null | undefined): TrialLine[] {
  // Only a successful trial probe may paint the three lights. A failed address/key/kind
  // check used to hard-code trial_*=false and still render a fake 「速率 ✓」.
  if (!result || result.probe_kind !== 'trial') return []
  if (result.ok === false || result.success === false) return []
  // A timeout or dropped request is not a context-window or JSON-format result.
  if (result.trial_answer === 'transport') {
    return [{ key: 'json', tone: 'fail', label: TIMEOUT_LINE }]
  }
  const contextOk = result.trial_context_ok === true
  const rateLimited = result.trial_rate_limited === true
  const lines: TrialLine[] = [
    {
      key: 'context',
      tone: contextOk ? 'ok' : 'fail',
      label: contextOk ? '上下文 ✓' : '上下文 ✗',
    },
    {
      key: 'rate',
      tone: rateLimited ? 'warn' : 'ok',
      label: rateLimited ? '速率 ⚠（出现限流，长视频建议降并发）' : '速率 ✓',
    },
  ]
  if (result.trial_answer === 'no_answer') {
    lines.push({ key: 'json', tone: 'fail', label: NO_ANSWER_LINE })
    return lines
  }
  // null means the attempt produced no visible answer to judge. Only an explicit
  // false is a format failure; only an explicit true is a format pass.
  if (result.trial_json_ok === true || result.trial_json_ok === false) {
    lines.push({
      key: 'json',
      tone: result.trial_json_ok ? 'ok' : 'fail',
      label: result.trial_json_ok ? '输出格式 ✓' : '输出格式 ✗',
    })
  }
  return lines
}

export function trialEstimateCopy(result: TrialResultLike | null | undefined): string {
  if (!result || result.probe_kind !== 'trial') return ''
  const n = result.trial_estimate_requests
  const m = result.trial_estimate_minutes
  if (typeof n !== 'number' || typeof m !== 'number') return ''
  // Concrete Chinese string remains the i18n key fallback when templates are missing.
  return `预计 30 分钟素材约需 ${n} 次请求、约 ${m} 分钟`
}

export function trialEstimateParts(result: TrialResultLike | null | undefined): { n: number; m: number } | null {
  if (!result || result.probe_kind !== 'trial') return null
  const n = result.trial_estimate_requests
  const m = result.trial_estimate_minutes
  if (typeof n !== 'number' || typeof m !== 'number') return null
  return { n, m }
}

/** Saved trial fields, used when the in-memory probe result is gone after a reload. */
export function trialResultFromConnection(connection: {
  trial_status?: string
  trial_context_ok?: boolean | null
  trial_rate_limited?: boolean | null
  trial_json_ok?: boolean | null
  trial_answer?: TrialResultLike['trial_answer']
  trial_avg_ms?: number | null
  trial_estimate_requests?: number | null
  trial_estimate_minutes?: number | null
} | null | undefined): TrialResultLike | null {
  if (!connection || !connection.trial_status || connection.trial_status === 'unchecked') return null
  return {
    ok: true,
    success: true,
    probe_kind: 'trial',
    trial_passed: connection.trial_status === 'passed',
    trial_context_ok: connection.trial_context_ok,
    trial_rate_limited: connection.trial_rate_limited,
    trial_json_ok: connection.trial_json_ok,
    trial_answer: connection.trial_answer,
    trial_avg_ms: connection.trial_avg_ms,
    trial_estimate_requests: connection.trial_estimate_requests,
    trial_estimate_minutes: connection.trial_estimate_minutes,
  }
}

export function showTrialFailedBadge(connection: {
  trial_status?: string
  validation_status?: string
} | null | undefined): boolean {
  return connection?.trial_status === 'failed'
}

export function trialPassedOverall(result: TrialResultLike | null | undefined): boolean {
  return result?.probe_kind === 'trial' && result.trial_passed === true
}
