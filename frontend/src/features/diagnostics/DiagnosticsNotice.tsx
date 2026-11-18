import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { t } from '../../i18n'
import { useTranslation } from 'react-i18next'
import { Btn } from '../../ui'
import { diagnosticsApi } from '../../services/api'

/** X or Esc hides the card for this page session and does not record a choice. */
let dismissedThisSession = false

type Preference = { diagnostics: boolean; media: boolean; fullOriginal: boolean }

/** Disclosure only. Uploads already follow the saved or default preference. */
export default function DiagnosticsNotice() {
  useTranslation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const [busy, setBusy] = useState(false)
  const [reloadToken, setReloadToken] = useState(0)
  const preference = useRef<Preference | null>(null)

  useEffect(() => {
    if (dismissedThisSession) return
    let active = true
    diagnosticsApi.consent()
      .then((grant) => {
        if (!active || dismissedThisSession) return
        if (grant.notice_seen || grant.persisted) {
          setOpen(false)
          return
        }
        setLoadError(false)
        const on = grant.unreadable !== true
        preference.current = {
          diagnostics: on && grant.diagnostics,
          media: on && grant.media,
          fullOriginal: on && grant.full_original,
        }
        setOpen(true)
      })
      .catch(() => {
        if (!active || dismissedThisSession) return
        preference.current = null
        setLoadError(true)
        setOpen(true)
      })
    return () => { active = false }
  }, [reloadToken])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      const target = event.target
      if (target instanceof Element && target.closest("input, textarea, [contenteditable='true'], [role='dialog'][aria-modal='true']")) return
      dismissedThisSession = true
      setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const dismiss = () => {
    dismissedThisSession = true
    setOpen(false)
  }

  const allow = async () => {
    const current = preference.current
    if (!current || loadError) {
      dismiss()
      return
    }
    setBusy(true)
    try {
      await diagnosticsApi.setConsent({
        diagnostics: current.diagnostics,
        media: current.diagnostics && current.media,
        full_original: current.diagnostics && current.media && current.fullOriginal,
        informed: true,
      })
      window.dispatchEvent(new Event('autoclip-diagnostics-consent'))
      setOpen(false)
    } catch {
      message.warning(t('诊断设置没有保存，请重试。'))
    } finally {
      setBusy(false)
    }
  }

  const openSettings = () => {
    dismiss()
    navigate('/settings?section=diagnostics')
  }

  if (!open || typeof document === 'undefined') return null

  return createPortal(
    <aside className="ac-diagnostics-notice" role="region" aria-labelledby="ac-diagnostics-notice-title">
      <button type="button" className="ac-diagnostics-notice-x" aria-label={t('关闭')} onClick={dismiss}>×</button>
      <h3 id="ac-diagnostics-notice-title">{t('一起让 AutoClip 更好用')}</h3>
      <p>{t('任务失败时，我们会自动发送错误信息，帮助改善产品体验，内容不用于任何训练和其他途径，你可以随时在设置中关闭。')}</p>
      {loadError && (
        <p className="ac-note">
          {t('已保存的诊断选择读不出来。在你确认前不会上传。')}
          {' '}
          <button type="button" className="ac-diagnostics-notice-more" onClick={() => setReloadToken((value) => value + 1)}>{t('重新读取')}</button>
        </p>
      )}
      <div className="ac-diagnostics-notice-actions">
        <Btn size="sm" variant="cta" loading={busy} onClick={() => void allow()}>{t('允许')}</Btn>
        <Btn size="sm" className="ac-btn--quiet" disabled={busy} onClick={openSettings}>{t('设置')}</Btn>
      </div>
    </aside>,
    document.body,
  )
}
