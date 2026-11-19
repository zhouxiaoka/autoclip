import { useEffect, useRef, useState } from 'react'
import { message } from 'antd'
import { t } from '../../i18n'
import { useTranslation } from 'react-i18next'
import { Btn, Dialog } from '../../ui'
import { diagnosticsApi, type DiagnosticsCase, type DiagnosticsPreview } from '../../services/api'

/** One explicit submission. Media stays unchecked until the user selects it. */
export default function DiagnosticsDialog({ open, onClose, projectId, attemptId }: {
  open: boolean
  onClose: () => void
  projectId?: string
  attemptId?: string
}) {
  useTranslation()
  const [preview, setPreview] = useState<DiagnosticsPreview | null>(null)
  const [roles, setRoles] = useState<string[]>([])
  const [background, setBackground] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<DiagnosticsCase | null>(null)
  const [localSaveId, setLocalSaveId] = useState('')
  const session = useRef(0)

  useEffect(() => {
    if (!open || !projectId) return
    setRoles([])
    setBackground(false)
    setResult(null)
    setPreview(null)
    setLocalSaveId('')
    setBusy(false)
    let cancel = false
    diagnosticsApi.preview(projectId, attemptId || '')
      .then((value) => { if (!cancel) setPreview(value) })
      .catch(() => { if (!cancel) setPreview(null) })
    return () => { cancel = true; session.current++ }
  }, [open, projectId, attemptId])

  useEffect(() => {
    if (!open || !localSaveId) return
    let active = true
    let timer: ReturnType<typeof setTimeout>
    const check = async () => {
      try {
        const item = await diagnosticsApi.getCase(localSaveId)
        if (!active) return
        if (item.status === 'saved_local') {
          setResult(item)
          setLocalSaveId('')
          message.success(t('已保存到本机。'))
          return
        }
        if (!['queued', 'uploading', 'needs_endpoint', 'offline'].includes(item.status)) {
          setLocalSaveId('')
          setResult(null)
          message.error(t('保存失败，请重试'))
          return
        }
      } catch (error) {
        if (!active) return
        if ((error as { response?: { status?: number } }).response?.status === 404) {
          setResult(null)
          setLocalSaveId('')
          message.error(t('保存失败，请重试'))
          return
        }
      }
      timer = setTimeout(check, 1000)
    }
    void check()
    return () => { active = false; clearTimeout(timer) }
  }, [open, localSaveId])

  const toggle = (role: string) => {
    setRoles((current) => current.includes(role) ? current.filter((item) => item !== role) : [...current, role])
  }

  const resolvedAttemptId = attemptId || preview?.manifest.attempt?.attempt_id || ''

  const send = async (saveLocal: boolean) => {
    if (!projectId || !resolvedAttemptId) return
    const currentSession = session.current
    setBusy(true)
    try {
      const value = await diagnosticsApi.submit({
        project_id: projectId,
        attempt_id: resolvedAttemptId,
        roles,
        informed: true,
        full_original_ack: roles.includes('original'),
        subtitle_ack: roles.includes('subtitle'),
        also_enable_background: background,
        save_local: saveLocal,
      })
      if (session.current !== currentSession) return
      setResult(value)
      if (value.status === 'saved_local') message.success(t('已保存到本机。'))
      else if (saveLocal) setLocalSaveId(value.id)
      else message.success(t('诊断已排队'))
    } catch (error) {
      if (session.current !== currentSession) return
      const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      message.error(detail === 'notice_required' ? t('请先在启动说明里确认是否自动发送。') : t('诊断没有提交'))
    } finally {
      if (session.current === currentSession) setBusy(false)
    }
  }

  const attempt = preview?.manifest.attempt
  const available = new Set((preview?.files || []).filter((file) => !file.rejected).map((file) => file.role))

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t('提交诊断')}
      description={t('看看将要发送的内容。这一次的素材需要逐项勾选，不会自动带上。本地视频在确认说明之后会压缩并上传短片段；完整原片默认关闭。视频链接只发送清洗后的链接，不发送下载下来的视频。已上传的诊断会在 14 天后自动删除。用于排查和改进，不会用于训练模型。')}
      footer={
        <div className="right">
          <Btn size="sm" onClick={onClose}>{t('关闭')}</Btn>
          {!result && <Btn size="sm" disabled={busy || !resolvedAttemptId} onClick={() => void send(true)}>{t('保存到本机')}</Btn>}
          {!result && <Btn size="sm" variant="cta" loading={busy} disabled={!resolvedAttemptId} onClick={() => void send(false)}>{t('我将对照清单再提交')}</Btn>}
          {result?.id && <Btn size="sm" onClick={() => void diagnosticsApi.remove(result.id).then(onClose).catch(() => message.error(t('删除失败')))}>{localSaveId || result.status === 'saved_local' ? t('删除') : t('删除已上传的诊断')}</Btn>}
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {!resolvedAttemptId && <p className="ac-note">{t('这次失败没有可关联的尝试编号，仍然可以写下反馈。')}</p>}
        {attempt && (
          <div className="ac-context" title={t('将随诊断一起发送的字段')}>
            {attempt.error_code && <span>{attempt.error_code}</span>}
            {attempt.failure_stage && <span>{attempt.failure_stage}</span>}
            {typeof attempt.sequence === 'number' && <span>{`#${attempt.sequence}`}</span>}
            {preview?.manifest.source_link && <span>{preview.manifest.source_link}</span>}
          </div>
        )}
        <p className="ac-note">{t('不含 API 密钥、字幕正文、项目名或个人路径。自动发送的是脱敏诊断；完整原片和短片段可以单独关闭。')}</p>
        <label className="ac-note"><input type="checkbox" checked={roles.includes('excerpt')} disabled={!available.has('excerpt')} onChange={() => toggle('excerpt')} /> {t('短片段（压缩后约 60 秒，有失败时间就围着它截取）')}</label>
        <label className="ac-note"><input type="checkbox" checked={roles.includes('original')} disabled={!available.has('original')} onChange={() => toggle('original')} /> {t('完整原片（这一次需要勾选）')}</label>
        <label className="ac-note"><input type="checkbox" checked={roles.includes('subtitle')} disabled={!available.has('subtitle')} onChange={() => toggle('subtitle')} /> {t('字幕文本（默认不发送）')}</label>
        <label className="ac-note"><input type="checkbox" checked={background} onChange={(event) => setBackground(event.target.checked)} /> {t('以后的失败也自动发送脱敏诊断')}</label>
        <p className="ac-note">{t('只对打开这项之后的新失败生效，不会补传以前的失败。')}</p>
        {localSaveId && <p className="ac-note" role="status">{t('正在处理中，请稍候...')}</p>}
        {result?.export_path && <p className="ac-note" role="status">{result.export_path}</p>}
      </div>
    </Dialog>
  )
}
