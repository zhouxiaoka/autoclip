import { ReactNode } from 'react'
import { t } from '../../i18n'
import { Btn } from '../../ui'
import { llmFailureText } from '../../utils/llmFailure'
import { pageFailureAction, PageFailureInfo } from './failureAction'

export type FailureInfo = PageFailureInfo & { error?: string | null }
export type FailureButton = { key: 'continue' | 'settings' | 'retry'; label: string; cta: boolean }
export type FailurePlan = { message: string; destination: string | null; buttons: FailureButton[] }

/** The failed step's state, computed once (code health): one message, each button at most once, explicit order.*/
export function failurePlan(info: FailureInfo, canRetry: boolean, returnedFromSettings: boolean): FailurePlan {
  const action = pageFailureAction(info)
  if (action.kind === 'retry') return { message: llmFailureText(info.error, info.error_code), destination: null, buttons: canRetry ? [{ key: 'retry', label: '重试', cta: false }] : [] }
  const resume = returnedFromSettings && canRetry  // back from a successful save: 「继续制作」 leads
  const buttons: FailureButton[] = [{ key: 'settings', label: '去设置', cta: !resume }]
  if (canRetry) buttons[resume ? 'unshift' : 'push']({ key: 'continue', label: '继续制作', cta: resume })
  return { message: action.reason, destination: action.destination, buttons }
}

export default function FailureActions({ info, canRetry, returnedFromSettings, busy, retrying, onRetry, onSettings, children }: {
  info: FailureInfo; canRetry: boolean; returnedFromSettings: boolean; busy: boolean; retrying: boolean
  onRetry: () => void; onSettings: (destination: string) => void; children?: ReactNode
}) {
  const plan = failurePlan(info, canRetry, returnedFromSettings)
  return <>
    <span className="studio-error">{t(plan.message)}</span>
    <div className="studio-actions">
      {plan.buttons.map(b => <Btn key={b.key} variant={b.cta ? 'cta' : undefined} disabled={busy} loading={b.key !== 'settings' && retrying}
        onClick={b.key === 'settings' ? () => onSettings(plan.destination as string) : onRetry}>{t(b.label)}</Btn>)}
      {children}
    </div>
  </>
}
