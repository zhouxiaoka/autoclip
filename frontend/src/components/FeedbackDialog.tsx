import React, { useEffect, useMemo, useState } from 'react'
import { message } from 'antd'
import { useTranslation } from 'react-i18next'
import { Btn, Dialog, Icon, Segmented } from '../ui'
import {
  FEEDBACK_FORM_URL,
  FEEDBACK_ISSUES_URL,
  FeedbackCategory,
  FeedbackContext,
  collectLlmContext,
  resolveFeedbackSurvey,
  submitFeedback,
  trackFeedbackDismissed,
  trackFeedbackOpened,
} from '../analytics/feedback'
import { isAnalyticsEnabled } from '../analytics/posthog'
import { getRuntimeInfo } from '../analytics/lifecycle'
import { openExternalLink as openExternal } from '../utils/externalLinks'

interface FeedbackDialogProps {
  open: boolean
  onClose: () => void
  context: FeedbackContext
}

/**
 * 应用内反馈 — 设置页「反馈」与项目失败态共用。
 * 自动附带版本 / 系统 / 架构 / LLM provider & 模型 / 失败阶段与错误，用户只需写一句话。
 */
const FeedbackDialog: React.FC<FeedbackDialogProps> = ({ open, onClose, context }) => {
  const { t } = useTranslation()
  const [category, setCategory] = useState<FeedbackCategory>(context.source === 'failure' ? 'bug' : 'idea')
  const [text, setText] = useState('')
  const [contact, setContact] = useState('')
  const [sending, setSending] = useState(false)
  const [llm, setLlm] = useState<Pick<FeedbackContext, 'llm_provider' | 'llm_model' | 'llm_base_url'>>({})
  const [surveyReady, setSurveyReady] = useState<boolean | null>(null)
  const runtime = useMemo(() => getRuntimeInfo(), [])
  const analyticsOn = isAnalyticsEnabled()

  const fullContext: FeedbackContext = useMemo(() => ({ ...llm, ...context }), [llm, context])

  useEffect(() => {
    if (!open) return
    setText('')
    setContact('')
    setCategory(context.source === 'failure' ? 'bug' : 'idea')
    collectLlmContext().then(setLlm)
    resolveFeedbackSurvey().then((s) => {
      setSurveyReady(!!s)
      trackFeedbackOpened(context, s)
    })
  }, [open, context])

  const handleClose = () => {
    resolveFeedbackSurvey().then((s) => trackFeedbackDismissed(context, s))
    onClose()
  }

  const handleSend = async () => {
    if (text.trim().length < 4) {
      message.warning(t('feedbackDialog.minCharsNotice'))
      return
    }
    setSending(true)
    try {
      const ok = await submitFeedback({ category, text: text.trim(), contact: contact.trim() || undefined, context: fullContext })
      if (ok) {
        message.success(t('feedbackDialog.successNotice'))
        onClose()
      } else {
        message.info(t('feedbackDialog.analyticsDisabled'))
        void openExternal(FEEDBACK_FORM_URL)
      }
    } finally {
      setSending(false)
    }
  }

  const ctxChips: string[] = [
    runtime.version !== 'unknown' ? `v${runtime.version}` : 'dev',
    `${runtime.os}/${runtime.arch}`,
  ]
  if (fullContext.llm_provider) ctxChips.push(`${fullContext.llm_provider}${fullContext.llm_model ? ` · ${fullContext.llm_model}` : ''}`)
  if (fullContext.stage) ctxChips.push(`stage: ${fullContext.stage}`)

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      title={context.source === 'failure' ? t('feedbackDialog.titleFailure') : t('feedbackDialog.titleGeneral')}
      description={
        context.source === 'failure'
          ? t('feedbackDialog.descFailure')
          : t('feedbackDialog.descGeneral')
      }
      footer={
        <>
          <div style={{ display: 'flex', gap: 4 }}>
            <Btn variant="text" size="sm" onClick={() => openExternal(FEEDBACK_FORM_URL)}>{t('feedbackDialog.form')} <Icon.External size={12} /></Btn>
            <Btn variant="text" size="sm" onClick={() => openExternal(FEEDBACK_ISSUES_URL)}>{t('feedbackDialog.github')} <Icon.External size={12} /></Btn>
          </div>
          <div className="right">
            <Btn size="sm" onClick={handleClose}>{t('feedbackDialog.cancel')}</Btn>
            <Btn variant="cta" size="sm" style={{ height: 32, fontSize: 13, padding: '0 16px' }} loading={sending} onClick={handleSend}>
              {t('feedbackDialog.send')}
            </Btn>
          </div>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <Segmented
          size="sm"
          ariaLabel="反馈类型"
          value={category}
          onChange={setCategory}
          options={[
            { value: 'bug', label: t('feedbackDialog.categoryBug') },
            { value: 'idea', label: t('feedbackDialog.categoryIdea') },
            { value: 'other', label: t('feedbackDialog.categoryOther') },
          ]}
        />
        <textarea
          className="ac-input ac-textarea"
          autoFocus
          placeholder={
            category === 'bug'
              ? t('feedbackDialog.placeholderBug')
              : category === 'idea'
                ? t('feedbackDialog.placeholderIdea')
                : t('feedbackDialog.placeholderOther')
          }
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={2000}
        />
        {fullContext.error_message && (
          <div className="ac-input ac-input--mono" style={{ height: 'auto', padding: '8px 12px', color: 'var(--ac-sub)', background: 'var(--ac-line-2)', whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: 88, overflow: 'auto', fontSize: 11.5 }}>
            {fullContext.error_message}
          </div>
        )}
        <input
          className="ac-input"
          placeholder={t('feedbackDialog.contactPlaceholder')}
          value={contact}
          onChange={(e) => setContact(e.target.value)}
        />
        <div className="ac-context" title={t('feedbackDialog.contextTooltip')}>
          {ctxChips.map((c) => <span key={c}>{c}</span>)}
          {!analyticsOn && <span style={{ color: 'var(--ac-warn)' }}>{t('feedbackDialog.analyticsDisabledHint')}</span>}
          {analyticsOn && surveyReady === false && <span>{t('feedbackDialog.directReport')}</span>}
        </div>
      </div>
    </Dialog>
  )
}

export default FeedbackDialog
