/** F2 trial-run result lines + estimate copy. Pure helpers for the connection card. */

export type TrialResultLike = {
  probe_kind?: 'quick' | 'trial'
  trial_context_ok?: boolean | null
  trial_rate_limited?: boolean | null
  trial_json_ok?: boolean | null
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

export function trialLines(result: TrialResultLike | null | undefined): TrialLine[] {
  if (!result || result.probe_kind !== 'trial') return []
  const contextOk = result.trial_context_ok === true
  const rateLimited = result.trial_rate_limited === true
  const jsonOk = result.trial_json_ok === true
  return [
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
    {
      key: 'json',
      tone: jsonOk ? 'ok' : 'fail',
      label: jsonOk ? '输出格式 ✓' : '输出格式 ✗',
    },
  ]
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

export function showTrialFailedBadge(connection: {
  trial_status?: string
  validation_status?: string
} | null | undefined): boolean {
  return connection?.trial_status === 'failed'
}

export function trialPassedOverall(result: TrialResultLike | null | undefined): boolean {
  return result?.probe_kind === 'trial' && result.trial_passed === true
}
