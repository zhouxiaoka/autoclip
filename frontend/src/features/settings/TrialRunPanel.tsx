import { t } from '../../i18n'
import { useTranslation } from 'react-i18next'
import type { TrialResultLike } from './trialRunResult'
import { showTrialFailedBadge, trialEstimateParts, trialLines } from './trialRunResult'

/** Three-line trial result + estimate. Yellow badge when any check failed. */
export function TrialRunPanel({
  result,
  trialStatus,
}: {
  result?: TrialResultLike | null
  trialStatus?: 'passed' | 'failed' | 'unchecked'
}) {
  useTranslation()
  const lines = trialLines(result)
  const estimate = trialEstimateParts(result)
  const badge = showTrialFailedBadge({ trial_status: trialStatus })
    || (result?.probe_kind === 'trial' && result.trial_passed === false)
  if (!lines.length && !badge) return null
  return (
    <div className="ac-trial-run" data-testid="trial-run-panel">
      {badge && (
        <p className="ac-note ac-note--warn" role="status" data-testid="trial-failed-badge">
          {t('未通过试跑')}
        </p>
      )}
      {lines.length > 0 && (
        <ul className="ac-trial-run-lines" style={{ listStyle: 'none', padding: 0, margin: '8px 0' }}>
          {lines.map(line => (
            <li
              key={line.key}
              data-tone={line.tone}
              style={{
                color: line.tone === 'fail' ? 'var(--ac-danger, #b45309)' : line.tone === 'warn' ? '#a16207' : 'var(--ac-sub)',
                fontSize: 13,
                lineHeight: 1.6,
              }}
            >
              {t(line.label)}
            </li>
          ))}
        </ul>
      )}
      {estimate && (
        <p className="ac-note" data-testid="trial-estimate">
          {t('预计 30 分钟素材约需 {{n}} 次请求、约 {{m}} 分钟', { n: estimate.n, m: estimate.m })}
        </p>
      )}
    </div>
  )
}

export default TrialRunPanel
