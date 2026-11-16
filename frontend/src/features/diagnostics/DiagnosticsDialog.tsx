import { useEffect, useState } from 'react'
import { message } from 'antd'
import { t } from '../../i18n'
import { useTranslation } from 'react-i18next'
import { Btn, Dialog } from '../../ui'
import { diagnosticsApi, type DiagnosticsPreview } from '../../services/api'

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
  const [result, setResult] = useState<{ id: string; status: string; case_id?: string; export_path?: string } | null>(null)

  useEffect(() => {
    if (!open || !projectId) return
    setRoles([])
    setBackground(false)
    setResult(null)
    let cancel = false
    diagnosticsApi.preview(projectId, attemptId || '')
      .then((value) => { if (!cancel) setPreview(value) })
      .catch(() => { if (!cancel) setPreview(null) })
    return () => { cancel = true }
  }, [open, projectId, attemptId])

  const toggle = (role: string) => {
    setRoles((current) => current.includes(role) ? current.filter((item) => item !== role) : [...current, role])
  }

  const send = async (saveLocal: boolean) => {
    if (!projectId || !attemptId) return
    setBusy(true)
    try {
      const value = await diagnosticsApi.submit({
        project_id: projectId,
        attempt_id: attemptId,
        roles,
        informed: true,
        full_original_ack: roles.includes('original'),
        subtitle_ack: roles.includes('subtitle'),
        also_enable_background: background,
        save_local: saveLocal,
      })
      setResult(value)
      if (value.status === 'saved_local') message.success(t('没有配置上传地址，已改为保存到本机。'))
      else message.success(t('诊断已排队'))
    } catch {
      message.error(t('诊断没有提交'))
    } finally {
      setBusy(false)
    }
  }

  const attempt = preview?.manifest.attempt
  const available = new Set((preview?.files || []).filter((file) => !file.rejected).map((file) => file.role))

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t('提交诊断')}
      description={t('看看将要发送的内容。素材默认不包含，需要逐项勾选。用于排查和改进，不会用于训练模型。')}
      footer={
        <div className="right">
          <Btn size="sm" onClick={onClose}>{t('关闭')}</Btn>
          {!result && <Btn size="sm" disabled={busy || !attemptId} onClick={() => void send(true)}>{t('保存到本机')}</Btn>}
          {!result && <Btn size="sm" variant="cta" loading={busy} disabled={!attemptId} onClick={() => void send(false)}>{t('我将对照清单再提交')}</Btn>}
          {result?.id && <Btn size="sm" onClick={() => void diagnosticsApi.remove(result.id).then(() => { message.success(t('已取消上传')); onClose() })}>{t('删除已上传的诊断')}</Btn>}
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {!attemptId && <p className="ac-note">{t('这次失败没有可关联的尝试编号，仍然可以写下反馈。')}</p>}
        {attempt && (
          <div className="ac-context" title={t('将随诊断一起发送的字段')}>
            {attempt.error_code && <span>{attempt.error_code}</span>}
            {attempt.failure_stage && <span>{attempt.failure_stage}</span>}
            {typeof attempt.sequence === 'number' && <span>{`#${attempt.sequence}`}</span>}
          </div>
        )}
        <p className="ac-note">{t('不含 API 密钥、字幕正文、项目名或个人路径。未配置上传地址时不会发送。')}</p>
        <label className="ac-note"><input type="checkbox" checked={roles.includes('excerpt')} disabled={!available.has('excerpt')} onChange={() => toggle('excerpt')} /> {t('短片段（从片头截取，可能复现不了片尾的超时）')}</label>
        <label className="ac-note"><input type="checkbox" checked={roles.includes('original')} disabled={!available.has('original')} onChange={() => toggle('original')} /> {t('完整原片（单独同意）')}</label>
        <label className="ac-note"><input type="checkbox" checked={roles.includes('subtitle')} disabled={!available.has('subtitle')} onChange={() => toggle('subtitle')} /> {t('字幕文本（默认不发送）')}</label>
        <label className="ac-note"><input type="checkbox" checked={background} onChange={(event) => setBackground(event.target.checked)} /> {t('以后的失败也自动发送脱敏诊断')}</label>
        <p className="ac-note">{t('只对打开这项之后的新失败生效，不会补传以前的失败。')}</p>
        {result?.export_path && <p className="ac-note">{result.export_path}</p>}
      </div>
    </Dialog>
  )
}
