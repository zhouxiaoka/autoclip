import { ComponentType, ReactNode, useState } from 'react'
import { t } from '../../i18n'
import { Btn } from '../../ui'
import { diagnoseInsteadOfRetry, pageFailureAction, pageFailureText, presentedFailure, PageFailureInfo } from './failureAction'
import { WEAK_LOCAL_TIMELINE_REASON, weakLocalTimelineFailure } from '../../utils/timelineFailure'

type DiagnosePanelProps = {
  open: boolean
  onClose: () => void
  info: FailureInfo
  reason?: string | null
  onSettings: (destination: string) => void
}

export type FailureInfo = PageFailureInfo & { error?: string | null }
export type RepeatFailure = { count?: number | null; same_code?: boolean | null }
export type FailureButton = { key: 'continue' | 'settings' | 'retry' | 'diagnose'; label: string; cta: boolean }
export type FailurePlan = {
  message: string
  step: '下载' | '转写' | '分析' | '制作'
  billing: string | null
  destination: string | null
  buttons: FailureButton[]
}

/** Same error twice: 「看看哪里不对」 leads, and the bare retry drops to a secondary button.
 * A settings / continue plan already tells the user what to fix, so it stays as it is. */
function leadWithDiagnose(buttons: FailureButton[], repeat?: RepeatFailure | null): FailureButton[] {
  if (!diagnoseInsteadOfRetry(repeat) || buttons.some(button => button.key !== 'retry')) return buttons
  const next: FailureButton[] = [{ key: 'diagnose', label: '看看哪里不对', cta: true }]
  if (buttons.some(button => button.key === 'retry')) next.push({ key: 'retry', label: '重试', cta: false })
  return next
}

/** The failed step's state, computed once (code health): one message, each button at most once, explicit order.*/
export function failurePlan(info: FailureInfo, canRetry: boolean, returnedFromSettings: boolean, repeatFailure?: RepeatFailure | null): FailurePlan {
  const action = pageFailureAction(info)
  const finish = (plan: FailurePlan): FailurePlan => ({ ...plan, buttons: leadWithDiagnose(plan.buttons, repeatFailure) })
  if (action.kind === 'retry' && weakLocalTimelineFailure(info.error, info.error_code)) {
    const card = presentedFailure(info, WEAK_LOCAL_TIMELINE_REASON)
    return finish({
      message: card.reason, step: card.step, billing: null, destination: null,
      buttons: canRetry ? [{ key: 'retry', label: '重试', cta: false }] : [],
    })
  }
  const reason = action.kind === 'settings' && action.reason ? action.reason : pageFailureText(info)
  const card = presentedFailure(info, reason)
  if (action.kind === 'retry') return finish({ message: card.reason, step: card.step, billing: card.billing, destination: null, buttons: canRetry ? [{ key: 'retry', label: '重试', cta: false }] : [] })
  const resume = returnedFromSettings && canRetry  // back from a successful save: 「继续制作」 leads
  const buttons: FailureButton[] = [{ key: 'settings', label: action.label || '去设置', cta: !resume }]
  if (canRetry) buttons[resume ? 'unshift' : 'push']({ key: 'continue', label: '继续制作', cta: resume })
  return finish({ message: card.reason, step: card.step, billing: card.billing, destination: action.destination, buttons })
}

export default function FailureActions({ info, canRetry, returnedFromSettings, busy, retrying, onRetry, onSettings, repeatFailure, children }: {
  info: FailureInfo; canRetry: boolean; returnedFromSettings: boolean; busy: boolean; retrying: boolean
  onRetry: () => void; onSettings: (destination: string) => void; repeatFailure?: RepeatFailure | null; children?: ReactNode
}) {
  const plan = failurePlan(info, canRetry, returnedFromSettings, repeatFailure)
  const [diagnose, setDiagnose] = useState(false)
  // The panel imports the readiness client and the sample-project API. Load it on click so the
  // failure page does not pull axios while it is only showing 「重试」 or 「去设置」.
  const [Panel, setPanel] = useState<ComponentType<DiagnosePanelProps> | null>(null)
  const showDiagnose = () => {
    if (Panel) { setDiagnose(true); return }
    void import('./DiagnosePanel').then(mod => {
      setPanel(() => mod.default)
      setDiagnose(true)
    })
  }
  return <>
    <FailureCopyText step={plan.step} reason={plan.message} billing={plan.billing} />
    <div className="studio-actions">
      {plan.buttons.map(b => <Btn key={b.key} variant={b.cta ? 'cta' : undefined} disabled={busy} loading={b.key !== 'settings' && b.key !== 'diagnose' && retrying}
        onClick={b.key === 'settings' ? () => onSettings(plan.destination as string) : b.key === 'diagnose' ? showDiagnose : onRetry}>{t(b.label)}</Btn>)}
      {children}
    </div>
    {diagnose && Panel && <Panel open onClose={() => setDiagnose(false)} info={info} reason={plan.message} onSettings={onSettings} />}
  </>
}

/** Step + human reason + optional billing sentence. Never only 「错误」. */
export function FailureCopy({ info, message }: { info: FailureInfo; message: string }) {
  const card = presentedFailure(info, message)
  return <FailureCopyText step={card.step} reason={card.reason} billing={card.billing} />
}

function FailureCopyText({ step, reason, billing }: { step: string; reason: string; billing: string | null }) {
  return <>
    <span className="studio-error">{t(step)}：{t(reason)}</span>
    {billing ? <p className="studio-billing">{t(billing)}</p> : null}
  </>
}
