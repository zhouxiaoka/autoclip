import { useState } from 'react'
import { t } from '../../i18n'
import { Btn, Row, fmtDuration } from '../../ui'
import type { Draft } from './types'
import { editableCues, correctCaption, captionRetranslation } from './captionEdits'

/** Corrections belong to the draft; saving/exporting keeps previous videos intact. */
export default function CaptionCorrections({ draft, patch, onRetranslate, onSeek, busy = false }: {
  draft: Draft
  patch: (changes: Partial<Draft>) => void
  onRetranslate?: (index: number, packaging?: Draft['packaging']) => void
  onSeek?: (start: number, end: number) => void
  busy?: boolean
}) {
  const [selected, setSelected] = useState(0)
  const packaging = draft.packaging
  if (!packaging) return null
  const rows = editableCues(packaging)
  if (!rows.length) return null
  const index = Math.min(selected, rows.length - 1)
  const cue = rows[index]
  const source = cue.source_text || cue.original
  const change = (text: string) => patch({ packaging: correctCaption(packaging, cue, text) })
  const retry = () => { const request = captionRetranslation(packaging, cue); onRetranslate?.(request.index, request.packaging) }
  return <Row stack label={t('逐句校对')} hint={t('译文覆盖完整不代表意思正确。修改后请保存并重新导出。')}>
    <select className="ac-input" aria-label={t('选择字幕句子')} value={index} onChange={e => setSelected(Number(e.target.value))}>
      {rows.map((row, i) => <option key={`${row.source_id || row.start}-${i}`} value={i}>{i + 1} · {fmtDuration(row.start)} · {row.text.slice(0, 35)}</option>)}
    </select>
    {source && <p className="studio-muted" style={{ whiteSpace: 'pre-wrap' }}>{t('原句')}：{source}</p>}
    <textarea className="ac-input" rows={4} maxLength={600} aria-label={t('修改此句字幕')} value={cue.text} onChange={e => change(e.target.value)} />
    {!cue.text.trim() && <span role="alert" className="studio-error">{t('字幕不能为空')}</span>}
    {cue.manually_edited && <span className="studio-muted">{t('人工修改将随草稿保存，补译其他句子时保留。')}</span>}
    <div className="studio-actions">
      {onSeek && <Btn size="sm" onClick={() => onSeek(cue.start, cue.end)}>{t('试听原句')}</Btn>}
      {onRetranslate && packaging.source_language !== packaging.audience_language && packaging.translation_status !== 'not_required' &&
        <Btn size="sm" loading={busy} disabled={busy} onClick={retry}>{t('重译此句')}</Btn>}
    </div>
  </Row>
}
