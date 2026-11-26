import { useState } from 'react'
import { t } from '../../i18n'
import { Btn } from '../../ui'
import { OUTPUT_ISSUE_TAGS, trackOutputRating, trackOutputShare, type OutputIssueTag, type VariantProperties } from '../../analytics/studio'
import { submitFeedback } from '../../analytics/feedback'
import { openExternalLink } from '../../utils/externalLinks'
import { USE_CASE_URL } from './outputShare'

type Rating = 'ready' | 'needs_edit' | 'unusable'
type Trigger = 'card_dislike' | 'post_download'

const ISSUE_LABELS: Record<OutputIssueTag, string> = {
  text_overlap: '字幕/标题叠字',
  cover_text: '封面文字有误',
  bad_crop: '画面裁切不当',
  bad_selection: '切片选段不准',
  audio_sync: '字幕/音画问题',
}

/**
 * Light output feedback attached to a completed result card.
 * - `post_download`: three-level rating; selecting `needs_edit` / `unusable` opens bad-case tags.
 * - `card_dislike`: directly opens bad-case tags + optional one-line note without requiring download.
 */
export default function OutputFeedback({
  projectId,
  variant,
  trigger = 'post_download',
  onSubmitted,
  onDone,
}: {
  projectId: string
  variant: VariantProperties
  trigger?: Trigger
  onSubmitted?: () => void
  onDone: () => void
}) {
  const [step, setStep] = useState<'rate' | 'tags' | 'done'>(trigger === 'card_dislike' ? 'tags' : 'rate')
  const [rating, setRating] = useState<Rating>(trigger === 'card_dislike' ? 'unusable' : 'ready')
  const [selected, setSelected] = useState<OutputIssueTag[]>([])
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const toggleTag = (tag: OutputIssueTag) => {
    setSelected(prev => (prev.includes(tag) ? prev.filter(item => item !== tag) : [...prev, tag]))
  }

  const chooseRating = (value: Rating) => {
    setRating(value)
    if (value === 'ready') {
      trackOutputRating(projectId, { output_rating: value, rating_trigger: trigger, ...variant })
      setStep('done')
      onSubmitted?.()
      return
    }
    setStep('tags')
  }

  const submitTags = async () => {
    if (submitting) return
    setSubmitting(true)
    try {
      trackOutputRating(projectId, {
        output_rating: rating,
        rating_trigger: trigger,
        ...(selected.length ? { issue_tags: selected } : {}),
        ...variant,
      })
      const trimmed = note.trim()
      if (trimmed) {
        const metaParts = [
          variant.template ? `template=${variant.template}` : '',
          variant.strategy_id ? `platform=${variant.strategy_id}` : '',
          selected.length ? `tags=${selected.join(',')}` : '',
        ].filter(Boolean)
        const prefix = metaParts.length ? `[${metaParts.join(' ')}] ` : ''
        await submitFeedback({
          category: 'bug',
          text: `${prefix}${trimmed}`,
          context: {
            source: 'detail',
            stage: 'output_card',
            project_id: projectId,
          },
        }).catch(() => undefined)
      }
      setStep('done')
      onSubmitted?.()
    } finally {
      setSubmitting(false)
    }
  }

  if (step === 'rate') {
    return <div className="studio-output-feedback" role="group" aria-label={t('这条成片能直接用吗？')}>
      <span className="studio-output-hint">{t('这条成片能直接用吗？')}</span>
      <div className="studio-output-feedback-actions">
        <Btn size="sm" variant="text" onClick={() => chooseRating('ready')}>{t('能直接用')}</Btn>
        <Btn size="sm" variant="text" onClick={() => chooseRating('needs_edit')}>{t('改一下能用')}</Btn>
        <Btn size="sm" variant="text" onClick={() => chooseRating('unusable')}>{t('不能用')}</Btn>
        <Btn size="sm" variant="text" onClick={onDone} aria-label={t('关闭')}>×</Btn>
      </div>
    </div>
  }

  if (step === 'tags') {
    const canSubmit = selected.length > 0 || note.trim().length > 0
    return <div className="studio-output-feedback-panel" role="group" aria-label={t('哪里不够理想？（可多选）')}>
      <div className="studio-output-feedback-head">
        <span className="studio-output-feedback-title">{t('哪里不够理想？（可多选）')}</span>
        <button type="button" className="studio-output-feedback-close" onClick={onDone} aria-label={t('关闭')}>×</button>
      </div>
      <div className="studio-output-feedback-pills">
        {OUTPUT_ISSUE_TAGS.map(tag => {
          const active = selected.includes(tag)
          return <button
            key={tag}
            type="button"
            className={`studio-output-feedback-pill${active ? ' is-on' : ''}`}
            aria-pressed={active}
            onClick={() => toggleTag(tag)}
          >
            {active ? `✓ ${t(ISSUE_LABELS[tag])}` : t(ISSUE_LABELS[tag])}
          </button>
        })}
      </div>
      <input
        type="text"
        className="studio-output-feedback-input"
        maxLength={240}
        value={note}
        onChange={e => setNote(e.target.value)}
        placeholder={t('补充一句具体问题（选填）')}
        aria-label={t('补充一句具体问题（选填）')}
      />
      <div className="studio-output-feedback-foot">
        <span className="studio-output-feedback-privacy">{t('不含视频与字幕内容')}</span>
        <Btn size="sm" disabled={!canSubmit || submitting} onClick={() => void submitTags()}>
          {t('提交反馈')}
        </Btn>
      </div>
    </div>
  }

  if (rating !== 'ready') {
    return <div className="studio-output-feedback-done" role="status">
      <span>{t('已收到反馈，将用于优化模板与剪辑策略')}</span>
      <button type="button" className="studio-output-feedback-close" onClick={onDone} aria-label={t('关闭')}>×</button>
    </div>
  }

  return <div className="studio-output-feedback" role="status">
    <span className="studio-output-hint">{t('谢谢反馈。愿意把这条成片分享为使用案例吗？')}</span>
    <div className="studio-output-feedback-actions">
      <Btn size="sm" variant="text" onClick={() => { trackOutputShare(projectId, { share_target: 'use_case_discussion', ...variant }); void openExternalLink(USE_CASE_URL); onDone() }}>{t('分享使用案例')}</Btn>
      <Btn size="sm" variant="text" onClick={onDone}>{t('关闭')}</Btn>
    </div>
  </div>
}
