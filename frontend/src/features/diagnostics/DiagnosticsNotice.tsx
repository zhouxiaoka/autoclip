import { useEffect, useState } from 'react'
import { Switch, message } from 'antd'
import { t } from '../../i18n'
import { useTranslation } from 'react-i18next'
import { Btn, Dialog } from '../../ui'
import { diagnosticsApi } from '../../services/api'

/** Shown before any default upload. Closing it does not count as a choice. */
export default function DiagnosticsNotice() {
  useTranslation()
  const [open, setOpen] = useState(false)
  const [unreadable, setUnreadable] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const [diagnostics, setDiagnostics] = useState(true)
  const [media, setMedia] = useState(true)
  const [fullOriginal, setFullOriginal] = useState(false)
  const [busy, setBusy] = useState(false)
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    let active = true
    diagnosticsApi.consent()
      .then((grant) => {
        if (!active) return
        if (grant.notice_seen) {
          setOpen(false)
          return
        }
        setLoadError(false)
        setUnreadable(grant.unreadable === true)
        const on = grant.unreadable !== true
        setDiagnostics(on && grant.diagnostics)
        setMedia(on && grant.media)
        setFullOriginal(on && grant.full_original)
        setOpen(true)
      })
      .catch(() => {
        if (!active) return
        setLoadError(true)
        setUnreadable(true)
        setDiagnostics(false)
        setMedia(false)
        setFullOriginal(false)
        setOpen(true)
      })
    return () => { active = false }
  }, [reloadToken])

  const save = async (nextDiagnostics: boolean, nextMedia: boolean, nextOriginal: boolean) => {
    setBusy(true)
    try {
      await diagnosticsApi.setConsent({
        diagnostics: nextDiagnostics,
        media: nextMedia,
        full_original: nextOriginal,
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

  return (
    <Dialog
      open={open}
      onClose={() => {}}
      title={t('失败诊断会自动发送')}
      description={t('从这一版开始，新的安装会在失败后自动发送脱敏诊断，用来排查问题并改进产品，不会用来训练模型。这不是你以前单独同意过的记录；你现在就可以关闭。')}
      footer={
        <div className="right">
          {loadError && <Btn size="sm" disabled={busy} onClick={() => setReloadToken((value) => value + 1)}>{t('重新读取')}</Btn>}
          <Btn size="sm" disabled={busy} onClick={() => void save(false, false, false)}>{t('全部关闭')}</Btn>
          <Btn size="sm" variant="cta" loading={busy} onClick={() => void save(diagnostics, diagnostics && media, diagnostics && media && fullOriginal)}>{t('知道了，按当前选择继续')}</Btn>
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {unreadable && <p className="ac-note">{t('已保存的诊断选择读不出来。在你确认前不会上传。')}</p>}
        <p className="ac-note">{t('本地视频默认会压缩并上传这次失败附近的短片段。没有失败时间时，用片头约 60 秒。短片段可能包含私人内容。完整原片默认不上传，需要你打开开关。如果这次用的是视频链接，只发送清洗后的链接，不发送下载下来的视频。字幕正文不会自动上传。')}</p>
        <p className="ac-note">{t('已上传的诊断会在 14 天后自动删除。你可以在这条说明里关闭总开关或单独关闭素材。关闭总开关会取消还没完成的上传。')}</p>
        <label className="ac-note"><Switch checked={diagnostics} onChange={setDiagnostics} /> {t('帮助改进 AutoClip')}</label>
        <label className="ac-note"><Switch checked={media} disabled={!diagnostics} onChange={setMedia} /> {t('允许附带失败任务的片段')}</label>
        <label className="ac-note"><Switch checked={fullOriginal} disabled={!diagnostics || !media} onChange={setFullOriginal} /> {t('允许附带完整原片')}</label>
      </div>
    </Dialog>
  )
}
