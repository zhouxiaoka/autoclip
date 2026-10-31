import { ComponentType, ReactNode, useState } from 'react'
import { openExternalLink } from '../../utils/externalLinks'
import { t } from '../../i18n'
import { Btn } from '../../ui'
import {
  ADD_PROVIDER_HINT,
  diagnoseInsteadOfRetry,
  INSTALL_TRANSCRIPTION_LABEL,
  pageFailureAction,
  pageFailureText,
  presentedFailure,
  RECHARGE_HINT,
  RECHARGE_LABEL,
  SPONSOR_PROVIDERS,
  SWITCH_MODEL_LABEL,
  PageFailureInfo,
} from './failureAction'
import { WEAK_LOCAL_TIMELINE_REASON, weakLocalTimelineFailure } from '../../utils/timelineFailure'
import SwitchModelDialog from './SwitchModelDialog'
import type { SwitchModelOption } from './switchModelOptions'

type DiagnosePanelProps = {
  open: boolean
  onClose: () => void
  info: FailureInfo
  reason?: string | null
  onSettings: (destination: string) => void
}

export type FailureInfo = PageFailureInfo & { error?: string | null }
export type RepeatFailure = { count?: number | null; same_code?: boolean | null }
export type FailureButton = {
  key: 'continue' | 'settings' | 'retry' | 'fresh' | 'diagnose' | 'install_asr' | 'switch_model' | 'recharge'
  label: string
  cta: boolean
}
export type FailurePlan = {
  message: string
  step: '下载' | '转写' | '分析' | '制作'
  billing: string | null
  destination: string | null
  buttons: FailureButton[]
  actionKind: ReturnType<typeof pageFailureAction>['kind']
  rechargeProvider?: string
}

/** Same error twice: 「看看哪里不对」 leads, and the bare retry drops to a secondary button.
 * A settings / continue / switch / install plan already tells the user what to fix, so it stays. */
function leadWithDiagnose(buttons: FailureButton[], repeat?: RepeatFailure | null): FailureButton[] {
  if (!diagnoseInsteadOfRetry(repeat) || buttons.some(button => button.key !== 'retry')) return buttons
  const next: FailureButton[] = [{ key: 'diagnose', label: '看看哪里不对', cta: true }]
  if (buttons.some(button => button.key === 'retry')) next.push({ key: 'retry', label: '重试', cta: false })
  return next
}

export type ResumePoint = { point?: string | null; label?: string | null } | null

function retryLabel(resumePoint?: ResumePoint): string {
  const label = (resumePoint?.label || '').trim()
  return label || '重试'
}

function withFresh(buttons: FailureButton[], canRetry: boolean, resumePoint?: ResumePoint): FailureButton[] {
  if (!canRetry || !resumePoint?.point || resumePoint.point === 'none') return buttons
  if (buttons.some(b => b.key === 'fresh')) return buttons
  return [...buttons, { key: 'fresh', label: '从头重做', cta: false }]
}

/** The failed step's state, computed once: one message, each button at most once, explicit order. */
export function failurePlan(info: FailureInfo, canRetry: boolean, returnedFromSettings: boolean, repeatFailure?: RepeatFailure | null, resumePoint?: ResumePoint): FailurePlan {
  const action = pageFailureAction(info)
  const finish = (plan: FailurePlan): FailurePlan => ({
    ...plan,
    buttons: withFresh(leadWithDiagnose(plan.buttons, repeatFailure), canRetry, resumePoint),
  })
  if (action.kind === 'retry' && weakLocalTimelineFailure(info.error, info.error_code)) {
    const card = presentedFailure(info, WEAK_LOCAL_TIMELINE_REASON)
    return finish({
      message: card.reason, step: card.step, billing: null, destination: null, actionKind: 'retry',
      buttons: canRetry ? [{ key: 'retry', label: retryLabel(resumePoint), cta: false }] : [],
    })
  }
  if (action.kind === 'install_asr') {
    const card = presentedFailure(info, pageFailureText(info))
    const buttons: FailureButton[] = [{ key: 'install_asr', label: action.label || INSTALL_TRANSCRIPTION_LABEL, cta: true }]
    if (canRetry) buttons.push({ key: 'retry', label: '重试', cta: false })
    return finish({ message: card.reason, step: card.step, billing: card.billing, destination: action.destination, actionKind: 'install_asr', buttons })
  }
  if (action.kind === 'switch_model') {
    const card = presentedFailure(info, pageFailureText(info))
    const buttons: FailureButton[] = [{ key: 'switch_model', label: SWITCH_MODEL_LABEL, cta: true }]
    if (canRetry) buttons.push({ key: 'retry', label: '重试', cta: false })
    return finish({ message: card.reason, step: card.step, billing: card.billing, destination: null, actionKind: 'switch_model', buttons })
  }
  if (action.kind === 'recharge') {
    const sponsor = (SPONSOR_PROVIDERS as readonly string[]).includes(action.provider)
    const reason = sponsor ? RECHARGE_HINT : pageFailureText(info)
    const card = presentedFailure(info, reason)
    const buttons: FailureButton[] = [{ key: 'recharge', label: action.label || RECHARGE_LABEL, cta: true }]
    if (canRetry) buttons.push({ key: 'retry', label: '重试', cta: false })
    return finish({
      message: card.reason, step: card.step, billing: card.billing, destination: action.destination,
      actionKind: 'recharge', rechargeProvider: action.provider, buttons,
    })
  }
  const reason = action.kind === 'settings' && action.reason ? action.reason : pageFailureText(info)
  const card = presentedFailure(info, reason)
  if (action.kind === 'retry') {
    return finish({ message: card.reason, step: card.step, billing: card.billing, destination: null, actionKind: 'retry', buttons: canRetry ? [{ key: 'retry', label: retryLabel(resumePoint), cta: true }] : [] })
  }
  const resume = returnedFromSettings && canRetry
  const settingsLabel = action.reason === ADD_PROVIDER_HINT ? '去设置' : (action.label || '去设置')
  const buttons: FailureButton[] = [{ key: 'settings', label: settingsLabel, cta: !resume }]
  if (canRetry) buttons[resume ? 'unshift' : 'push']({ key: 'continue', label: '继续制作', cta: resume })
  return finish({ message: card.reason, step: card.step, billing: card.billing, destination: action.destination, actionKind: 'settings', buttons })
}

export default function FailureActions({
  info, canRetry, returnedFromSettings, busy, retrying, onRetry, onSettings, repeatFailure, children,
  switchOptions, onSwitchModel, onRecharge, resumePoint, onFreshRetry,
}: {
  info: FailureInfo; canRetry: boolean; returnedFromSettings: boolean; busy: boolean; retrying: boolean
  onRetry: () => void; onSettings: (destination: string) => void; repeatFailure?: RepeatFailure | null; children?: ReactNode
  switchOptions?: SwitchModelOption[]
  onSwitchModel?: (choice: { connectionId: string; model: string }) => void | Promise<void>
  onRecharge?: (provider: string) => void
  resumePoint?: ResumePoint
  onFreshRetry?: () => void
}) {
  const plan = failurePlan(info, canRetry, returnedFromSettings, repeatFailure, resumePoint)
  const [diagnose, setDiagnose] = useState(false)
  const [switchOpen, setSwitchOpen] = useState(false)
  const [switchBusy, setSwitchBusy] = useState(false)
  const [Panel, setPanel] = useState<ComponentType<DiagnosePanelProps> | null>(null)
  const showDiagnose = () => {
    if (Panel) { setDiagnose(true); return }
    void import('./DiagnosePanel').then(mod => {
      setPanel(() => mod.default)
      setDiagnose(true)
    })
  }
  const click = (key: FailureButton['key']) => {
    if (key === 'settings') return onSettings(plan.destination as string)
    if (key === 'install_asr') return onSettings(plan.destination as string)
    if (key === 'diagnose') return showDiagnose()
    if (key === 'switch_model') {
      if (switchOptions && switchOptions.length && onSwitchModel) { setSwitchOpen(true); return }
      return onSettings('/settings?section=analysis')
    }
    if (key === 'recharge') {
      const url = (plan.destination || '').trim()
      if (/^https?:\/\//i.test(url)) {
        void openExternalLink(url)
        return
      }
      if (plan.rechargeProvider && onRecharge) return onRecharge(plan.rechargeProvider)
      return onSettings(url || '/settings?section=analysis')
    }
    if (key === 'fresh') return (onFreshRetry || onRetry)()
    return onRetry()
  }
  return <>
    <FailureCopyText step={plan.step} reason={plan.message} billing={plan.billing} />
    {plan.actionKind === 'settings' && plan.message === ADD_PROVIDER_HINT ? null : null}
    <div className="studio-actions">
      {plan.buttons.map(b => (
        <Btn
          key={b.key}
          variant={b.cta ? 'cta' : undefined}
          disabled={busy || switchBusy}
          loading={b.key !== 'settings' && b.key !== 'diagnose' && b.key !== 'install_asr' && b.key !== 'switch_model' && b.key !== 'recharge' && b.key !== 'fresh' && retrying}
          onClick={() => click(b.key)}
        >{t(b.label)}</Btn>
      ))}
      {children}
    </div>
    {diagnose && Panel && <Panel open onClose={() => setDiagnose(false)} info={info} reason={plan.message} onSettings={onSettings} />}
    {switchOpen && (
      <SwitchModelDialog
        open={switchOpen}
        options={switchOptions || []}
        busy={switchBusy}
        onClose={() => setSwitchOpen(false)}
        onConfirm={async (choice) => {
          if (!onSwitchModel) return
          setSwitchBusy(true)
          try {
            await onSwitchModel(choice)
            setSwitchOpen(false)
          } finally {
            setSwitchBusy(false)
          }
        }}
      />
    )}
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
