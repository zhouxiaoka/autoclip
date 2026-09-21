import { t } from '../i18n'
import { useTranslation } from 'react-i18next'
import React, { useEffect, useMemo, useState } from 'react'
import { message } from 'antd'
import { Btn, Dialog, Icon, Segmented } from '../ui'
import {
  FEEDBACK_DISCUSSIONS_URL,
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
  useTranslation()
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
      message.warning(t("再多写几个字，我们才好定位问题"))
      return
    }
    setSending(true)
    try {
      const ok = await submitFeedback({ category, text: text.trim(), contact: contact.trim() || undefined, context: fullContext })
      if (ok) {
        message.success(t("已收到，感谢反馈"))
        onClose()
      } else {
        message.info(t("匿名统计已关闭，请到 GitHub 提交"))
        void openExternal(category === 'bug' ? FEEDBACK_ISSUES_URL : FEEDBACK_DISCUSSIONS_URL)
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
      title={context.source === 'failure' ? t("这次没出片，告诉我们哪里不对") : t("反馈")}
      description={
        context.source === 'failure'
          ? t("错误信息和运行环境会自动附上，你只需要补一句发生了什么。")
          : t("一句话就够。运行环境会自动附上，不包含视频内容与 API 密钥。")
      }
      footer={
        <>
          <div style={{ display: 'flex', gap: 4 }}>
            <Btn variant="text" size="sm" onClick={() => openExternal(category === 'bug' ? FEEDBACK_ISSUES_URL : FEEDBACK_DISCUSSIONS_URL)}>GitHub <Icon.External size={12} /></Btn>
          </div>
          <div className="right">
            <Btn size="sm" onClick={handleClose}>{t("取消")}</Btn>
            <Btn variant="cta" size="sm" style={{ height: 32, fontSize: 13, padding: '0 16px' }} loading={sending} onClick={handleSend}>{t("发送")}</Btn>
          </div>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <Segmented
          size="sm"
          ariaLabel={t("反馈类型")}
          value={category}
          onChange={setCategory}
          options={[
            { value: 'bug', label: t("出问题了") },
            { value: 'idea', label: t("想要功能") },
            { value: 'other', label: t("其他") },
          ]}
        />
        <textarea
          className="ac-input ac-textarea"
          autoFocus
          placeholder={
            category === 'bug'
              ? t("发生了什么？做了哪一步、预期是什么、实际看到什么。")
              : category === 'idea'
                ? t("你想让 AutoClip 帮你做到什么？")
                : t("想说什么都可以。")
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
          placeholder={t("联系方式（可选，邮箱）")}
          value={contact}
          onChange={(e) => setContact(e.target.value)}
        />
        <div className="ac-context" title={t("将随反馈一起发送的上下文")}>
          {ctxChips.map((c) => <span key={c}>{c}</span>)}
          {!analyticsOn && <span style={{ color: 'var(--ac-warn)' }}>{t("匿名统计已关闭 · 请用 GitHub")}</span>}
          {analyticsOn && surveyReady === false && <span>{t("· 直接上报")}</span>}
        </div>
      </div>
    </Dialog>
  )
}

export default FeedbackDialog
