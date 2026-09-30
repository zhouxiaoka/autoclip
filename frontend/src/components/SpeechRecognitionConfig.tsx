import { t } from '../i18n'
import { useTranslation } from 'react-i18next'
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Popconfirm, Select, message } from 'antd'
import { speechApi, WhisperRuntimeStatus, WhisperModel } from '../services/api'
import { Btn, ProgressLine, Row, StatusDot } from '../ui'

interface SpeechRecognitionConfigProps {
  hideProvider?: boolean
  selectedModel?: string
  onModelChange?: (model: string) => void
}

// Whisper 运行时 + 模型管理 — Calm Premium 行式布局（见 DESIGN.md）
const SpeechRecognitionConfig: React.FC<SpeechRecognitionConfigProps> = ({ selectedModel = 'base', onModelChange, hideProvider = false }) => {
  useTranslation()
  const [runtime, setRuntime] = useState<WhisperRuntimeStatus | null>(null)
  const [models, setModels] = useState<WhisperModel[]>([])
  const [loading, setLoading] = useState(true)
  const pendingModel = useRef<string | null>(null)
  const [preparing, setPreparing] = useState(false)
  const timer = useRef<number | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [rt, ms] = await Promise.all([speechApi.getRuntimeStatus(), speechApi.getModels()])
      setRuntime(rt)
      setModels(Array.isArray(ms) ? ms : [])
    } catch {
      // Keep the existing status until the next refresh.
    } finally {
      setLoading(false)
    }
  }, [])

  // 安装中或有模型下载中时，加快轮询
  const needsFastPoll = (rt: WhisperRuntimeStatus | null, ms: WhisperModel[]) =>
    rt?.status === 'installing' || ms.some((m) => m.status === 'downloading')

  useEffect(() => {
    refresh()
    return () => { if (timer.current) window.clearInterval(timer.current) }
  }, [refresh])

  useEffect(() => {
    if (timer.current) window.clearInterval(timer.current)
    timer.current = window.setInterval(refresh, needsFastPoll(runtime, models) ? 2000 : 15000)
    return () => { if (timer.current) window.clearInterval(timer.current) }
  }, [runtime, models, refresh])

  const handleInstall = async () => {
    try {
      await speechApi.installRuntime()
      message.info(t("已开始安装"))
      setRuntime((p) => (p ? { ...p, status: 'installing', progress: 5 } : p))
      refresh()
    } catch (e: any) {
      pendingModel.current = null
      setPreparing(false)
      message.error(e?.response?.data?.detail || t("安装失败"))
    }
  }

  const handleUninstall = async () => {
    try {
      await speechApi.uninstallRuntime()
      message.success(t("已卸载"))
      refresh()
    } catch {
      message.error(t("卸载失败"))
    }
  }

  const handleDownload = async (model: string) => {
    try {
      await speechApi.downloadModel(model)
      message.info(t("开始下载 {{value1}}", { value1: model }))
      setModels((prev) => prev.map((m) => (m.name === model ? { ...m, status: 'downloading' } : m)))
      refresh()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("下载失败"))
    }
  }

  const handleDelete = async (model: string) => {
    try {
      await speechApi.deleteModel(model)
      message.success(t("已删除 {{value1}}", { value1: model }))
      refresh()
    } catch {
      message.error(t("删除失败"))
    }
  }

  useEffect(() => {
    if (runtime?.status === 'error') { pendingModel.current = null; setPreparing(false) }
    if (runtime?.status === 'installed' && pendingModel.current) {
      const model = pendingModel.current
      pendingModel.current = null
      void handleDownload(model).finally(() => setPreparing(false))
    }
  }, [runtime?.status])

  const selected = models.find(m => m.name === selectedModel)
  const installed = runtime?.status === 'installed'
  const installing = runtime?.status === 'installing'
  const downloading = selected?.status === 'downloading'
  const ready = installed && selected?.status === 'downloaded'
  const prepare = async () => {
    setPreparing(true)
    if (installed) {
      await handleDownload(selectedModel)
      setPreparing(false)
    } else {
      pendingModel.current = selectedModel
      await handleInstall()
    }
  }

  return <div className="ac-rows">
    {!hideProvider && <Row label={t('提供商')} hint={t('在本机把音频转成字幕，不上传音频，无需 API Key。')}>
      <span>{t('Whisper · 本地')}</span>
    </Row>}
    <Row wide label={t('转写模型')} hint={t('视频没有字幕时使用。模型越大通常越准确，也需要更多时间和内存。')}>
      <Select aria-label={t('转写模型')} style={{ width: '100%' }} value={selectedModel} loading={loading} disabled={preparing || installing || downloading}
        options={(models.length ? models.map(m => ({ value: m.name, label: `${m.name} · ${m.size}` })) : ['tiny', 'base', 'small', 'medium', 'large-v3'].map(name => ({ value: name, label: name })))}
        onChange={onModelChange} />
    </Row>
    <Row label={ready ? t('模型已就绪') : t('准备本地模型')} hint={ready ? t('保存设置后，新任务将使用这个模型。') : runtime?.status === 'error' ? runtime.message : selected?.status === 'error' && installed ? selected.errorMessage : t('首次使用需下载模型和必要组件，之后可在本机转写。')}>
      {ready ? <StatusDot tone="ok" label={t('已就绪')} /> : installing || downloading || preparing ? <div style={{ width: 220 }}>
        <ProgressLine percent={installing ? runtime?.progress ?? 5 : selected?.downloadProgress ?? 0} />
        <span className="ac-hint">{installing ? t('正在准备组件…') : t('正在下载模型…')}</span>
      </div> : <Btn size="sm" disabled={runtime?.platform_supported === false || loading || !runtime} onClick={() => void prepare()}>{t('准备模型')}</Btn>}
    </Row>
    {!runtime && !loading && <p className="ac-note">{t('暂时无法读取本地模型状态。')} <Btn variant="text" size="sm" onClick={() => void refresh()}>{t('重试')}</Btn></p>}
    <details className="ac-disclosure"><summary>{t('本地模型管理')}</summary>
      {models.filter(m => m.status === 'downloaded').map(m => <Row key={m.name} label={`${m.name} · ${m.size}`}>
        <Popconfirm title={t('删除模型 {{value1}}？', { value1: m.name })} onConfirm={() => handleDelete(m.name)} okText={t('删除')} cancelText={t('取消')}><Btn variant="danger" size="sm">{t('删除')}</Btn></Popconfirm>
      </Row>)}
      {installed && <Row label={t('本地转写组件')}><Popconfirm title={t('卸载 Whisper 运行时？已下载的模型不会被删除。')} onConfirm={handleUninstall} okText={t('卸载')} cancelText={t('取消')}><Btn variant="danger" size="sm">{t('卸载')}</Btn></Popconfirm></Row>}
      {runtime?.log_tail && <pre className="ac-note" style={{ maxHeight: 120, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{runtime.log_tail}</pre>}
    </details>
  </div>
}

export default SpeechRecognitionConfig
