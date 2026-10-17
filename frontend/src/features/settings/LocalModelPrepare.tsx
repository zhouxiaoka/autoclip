import type { ReactNode } from 'react'
import { t } from '../../i18n'
import { Btn, ProgressLine, Row, StatusDot } from '../../ui'

/**
 * Shared first-enable row for local ASR (Whisper + SenseVoice):
 * prepare button, thin progress, then a ready dot. No separate wizard.
 */
export default function LocalModelPrepare({
  ready,
  preparing,
  progress,
  busy,
  hint,
  busyHint,
  error,
  onPrepare,
  disabled,
}: {
  ready: boolean
  preparing: boolean
  progress?: number
  busy?: boolean
  hint: ReactNode
  busyHint: string
  error?: string
  onPrepare: () => void
  disabled?: boolean
}) {
  return <>
    <Row label={ready ? t('模型已就绪') : t('准备本地模型')} hint={ready ? t('保存设置后，新任务将使用这个模型。') : hint}>
      {ready ? <StatusDot tone="ok" label={t('已就绪')} />
        : preparing ? <div style={{ width: 220 }}>
          <ProgressLine percent={progress ?? 0} busy={busy} />
          <span className="ac-hint">{busyHint}</span>
        </div>
        : <Btn size="sm" disabled={disabled} onClick={onPrepare}>{t('准备模型')}</Btn>}
    </Row>
    {!!error && <p className="ac-note" role="alert">{error}</p>}
  </>
}
