import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { t } from '../../i18n'
import { Btn, Dialog, StatusDot } from '../../ui'
import { trackDiagnoseAction, trackDiagnoseOpened } from '../../analytics/studio'
import { studioApi } from './api'
import { presentedFailure, suggestedAction, type PageFailureInfo, type SuggestedAction } from './failureAction'
import type { ImportReadiness } from './importReadiness'
import { openExample } from './openExample'

type FailureInfo = PageFailureInfo & { error?: string | null }

const CHECKS = [
  ['analysis', '分析模型'],
  ['transcription', '转写'],
  ['visual', '画面理解'],
  ['ffmpeg', '视频处理'],
] as const

export type ReadinessRow = { key: string; tone: 'ok' | 'error' | 'muted'; name: string; status: string }

/** Four readiness rows CreativeImport already probes: analysis, transcription, visual, ffmpeg. */
export function readinessRows(report?: ImportReadiness | null): ReadinessRow[] {
  return CHECKS.map(([key, name]) => {
    const check = report?.checks?.[key]
    if (!check || typeof check.ok !== 'boolean') return { key, tone: 'muted', name, status: '还在确认' }
    if (check.ok) return { key, tone: 'ok', name, status: '已就绪' }
    return { key, tone: 'error', name, status: '还没准备好' }
  })
}

export default function DiagnosePanel({ open, onClose, info, reason, onSettings, readiness }: {
  open: boolean
  onClose: () => void
  info: FailureInfo
  reason?: string | null
  onSettings: (destination: string) => void
  /** Tests pass a report. Omitted: the panel loads the same /studio/readiness probe as import. */
  readiness?: ImportReadiness | null
}) {
  const navigate = useNavigate()
  const [fetched, setFetched] = useState<ImportReadiness | null | undefined>(undefined)
  const [exampleBusy, setExampleBusy] = useState(false)
  const [exampleError, setExampleError] = useState('')
  const suggestion = suggestedAction(info.error_code, info.upstream_error_type, info.failure_stage)
  const card = presentedFailure(info, reason)
  const report = readiness !== undefined ? readiness : fetched

  useEffect(() => {
    if (!open) return
    trackDiagnoseOpened(info.error_code, suggestion?.id)
  }, [open, info.error_code, info.upstream_error_type, info.failure_stage, suggestion?.id])

  useEffect(() => {
    if (!open || readiness !== undefined) return
    let cancel = false
    setFetched(undefined)
    void studioApi.readiness()
      .then(value => { if (!cancel) setFetched(value) })
      .catch(() => { if (!cancel) setFetched(null) })
    return () => { cancel = true }
  }, [open, readiness])

  const runSuggestion = (next: SuggestedAction) => {
    if (next.kind === 'note' || next.id === 'keep_window') return
    trackDiagnoseAction(next.id)
    onClose()
    if (next.kind === 'settings' && next.destination) onSettings(next.destination)
    else if (next.kind === 'home') navigate(next.destination || '/')
  }

  const tryExample = async () => {
    trackDiagnoseAction('example')
    setExampleBusy(true)
    setExampleError('')
    try {
      await openExample(navigate)
    } catch {
      setExampleError(t('示例项目暂时不可用'))
    } finally {
      setExampleBusy(false)
    }
  }

  return <Dialog open={open} onClose={onClose} title={t('看看哪里不对')}
    description={t('同一类错误已经连续出现。先看准备情况，再决定要不要重试。')}
    footer={<div className="studio-actions">
      <Btn disabled={exampleBusy} onClick={onClose}>{t('关闭')}</Btn>
      <Btn loading={exampleBusy} onClick={() => void tryExample()}>{t('用示例视频试一次')}</Btn>
    </div>}>
    <div className="studio-diagnose">
      <p className="studio-muted">{t('准备情况')}</p>
      <div className="studio-readiness" role="status" aria-label={t('准备情况')}>
        {readinessRows(report).map(row => <div className="studio-readiness-row" key={row.key}>
          <StatusDot tone={row.tone} label={`${t(row.name)} · ${t(row.status)}`} />
        </div>)}
      </div>
      <p className="studio-muted">{t('上次失败')}</p>
      <p className="studio-error">{t(card.step)}：{t(card.reason)}</p>
      {suggestion && <>
        <p className="studio-muted">{t('建议先做这一步')}</p>
        {suggestion.kind === 'note'
          ? <p>{t(suggestion.label)}</p>
          : <Btn variant="cta" onClick={() => runSuggestion(suggestion)}>{t(suggestion.label)}</Btn>}
      </>}
      {exampleError && <p className="studio-error" role="alert">{exampleError}</p>}
    </div>
  </Dialog>
}
