import { useEffect, useState } from 'react'
import { t } from '../../i18n'
import { Btn, Row, StatusDot } from '../../ui'
import api from '../../services/api'

type SenseVoiceStatus = { status: 'not_installed' | 'installing' | 'ready' | 'error'; message: string }

export default function SenseVoiceConfig() {
  const [runtime, setRuntime] = useState<SenseVoiceStatus | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    let active = true
    const refresh = async () => {
      try {
        const value = await api.get<unknown, SenseVoiceStatus>('/sensevoice/status')
        if (active) { setRuntime(value); setError('') }
      } catch { if (active) setError(t('暂时无法读取本地模型状态。')) }
    }
    void refresh()
    const timer = window.setInterval(() => void refresh(), 3000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])
  const act = async (remove = false) => {
    setBusy(true)
    try {
      const value = remove ? await api.delete<unknown, SenseVoiceStatus>('/sensevoice')
        : await api.post<unknown, SenseVoiceStatus>('/sensevoice/prepare')
      setRuntime(value); setError('')
    } catch { setError(t('操作失败，请稍后重试。')) }
    finally { setBusy(false) }
  }
  const preparing = runtime?.status === 'installing'
  return <div className="ac-rows">
    <Row label={t('转写模型')} hint={t('支持中文、粤语、英语、日语和韩语，使用词级时间戳生成字幕。')}><span>SenseVoiceSmall</span></Row>
    <Row label={runtime?.status === 'ready' ? t('模型已就绪') : t('准备本地模型')}
      hint={runtime?.status === 'ready' ? t('保存设置后，新任务将使用这个模型。') : t('首次需联网下载组件和模型，请预留至少 8 GB 磁盘空间；准备完成后转写不上传音频。')}>
      {runtime?.status === 'ready' ? <StatusDot tone="ok" label={t('已就绪')} />
        : preparing ? <StatusDot tone="accent" label={t('正在准备组件与模型…')} />
        : <Btn size="sm" disabled={!runtime || busy} onClick={() => void act()}>{t('准备模型')}</Btn>}
    </Row>
    {(error || runtime?.status === 'error') && <p className="ac-note" role="alert">{error || t('模型准备失败，请检查网络和磁盘空间后重试。')}</p>}
    <p className="ac-note">{t('仅安装所需模型，不启用说话人分离。')} <a href="https://huggingface.co/FunAudioLLM/SenseVoiceSmall" target="_blank" rel="noreferrer">{t('模型与许可说明')}</a></p>
    {runtime?.status === 'ready' && <details className="ac-disclosure"><summary>{t('高级')}</summary>
      <Row label={t('删除 SenseVoice 组件与模型')} hint={t('删除后需要重新下载才能使用。')}>
        <Btn variant="danger" size="sm" disabled={busy} onClick={() => void act(true)}>{t('删除')}</Btn>
      </Row>
    </details>}
  </div>
}
