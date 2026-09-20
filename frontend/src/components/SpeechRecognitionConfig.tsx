import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Popconfirm, message } from 'antd'
import { useTranslation } from 'react-i18next'
import { speechApi, WhisperRuntimeStatus, WhisperModel } from '../services/api'
import { Btn, ProgressLine, Row, StatusDot } from '../ui'

interface SpeechRecognitionConfigProps {
  config?: Record<string, unknown>
  onConfigChange?: (config: Record<string, unknown>) => void
}

// Whisper 运行时 + 模型管理 — Calm Premium 行式布局（见 DESIGN.md）
const SpeechRecognitionConfig: React.FC<SpeechRecognitionConfigProps> = () => {
  const { t } = useTranslation()
  const [runtime, setRuntime] = useState<WhisperRuntimeStatus | null>(null)
  const [models, setModels] = useState<WhisperModel[]>([])
  const [loading, setLoading] = useState(true)
  const timer = useRef<number | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [rt, ms] = await Promise.all([speechApi.getRuntimeStatus(), speechApi.getModels()])
      setRuntime(rt)
      setModels(Array.isArray(ms) ? ms : [])
    } catch {
      // 后端可能尚未就绪，静默重试
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
      const r = await speechApi.installRuntime()
      message.info(r.message || t('settings.speech.installedSuccess'))
      setRuntime((p) => (p ? { ...p, status: 'installing', progress: 5 } : p))
      refresh()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t('settings.speech.installFailed'))
    }
  }

  const handleUninstall = async () => {
    try {
      const r = await speechApi.uninstallRuntime()
      message.success(r.message || t('settings.speech.uninstalledSuccess'))
      refresh()
    } catch {
      message.error(t('settings.speech.uninstallFailed'))
    }
  }

  const handleDownload = async (model: string) => {
    try {
      await speechApi.downloadModel(model)
      message.info(t('settings.speech.startDownload', { model }))
      setModels((prev) => prev.map((m) => (m.name === model ? { ...m, status: 'downloading' } : m)))
      refresh()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t('settings.speech.downloadFailed'))
    }
  }

  const handleDelete = async (model: string) => {
    try {
      await speechApi.deleteModel(model)
      message.success(t('settings.speech.deletedSuccess', { model }))
      refresh()
    } catch {
      message.error(t('settings.speech.deleteFailed'))
    }
  }

  if (loading) return <div className="ac-hint">{t('settings.speech.readingStatus')}</div>

  const installed = runtime?.status === 'installed'
  const installing = runtime?.status === 'installing'
  const supported = runtime?.platform_supported !== false

  return (
    <>
      <div className="ac-rows">
        <Row
          top
          label={t('settings.speech.runtime')}
          hint={
            !supported ? t('settings.speech.notSupported')
              : installed ? `${t('settings.speech.installed')}${runtime?.packages?.length ? ` (${runtime.packages.join(', ')})` : ''}。`
              : installing ? (runtime?.message || t('settings.speech.installing'))
              : runtime?.status === 'error' ? `${t('settings.speech.installError')}${runtime?.message || ''}`
              : t('settings.speech.onDemandHint')
          }
        >
          {installed && (
            <>
              <StatusDot tone="ok" label={t('settings.speech.statusDownloaded')} />
              <Popconfirm title={t('settings.speech.uninstallConfirm')} onConfirm={handleUninstall} okText={t('settings.speech.uninstall')} cancelText={t('common.cancel')}>
                <Btn variant="danger" size="sm">{t('settings.speech.uninstall')}</Btn>
              </Popconfirm>
            </>
          )}
          {installing && (
            <div style={{ width: 220 }}>
              <ProgressLine percent={runtime?.progress ?? 5} />
              <div className="ac-hint" style={{ textAlign: 'right', fontFamily: 'var(--ac-font-mono)' }}>{Math.round(runtime?.progress ?? 5)}%</div>
            </div>
          )}
          {runtime?.status === 'not_installed' && (
            <Btn variant="cta" size="sm" style={{ height: 32, fontSize: 13, padding: '0 16px' }} onClick={handleInstall} disabled={!supported}>{t('settings.speech.install')}</Btn>
          )}
          {runtime?.status === 'error' && (
            <Btn size="sm" onClick={handleInstall} disabled={!supported}>{t('common.retry')}</Btn>
          )}
        </Row>
      </div>

      {installing && runtime?.log_tail && (
        <pre className="ac-input ac-input--mono" style={{ height: 'auto', maxHeight: 120, overflow: 'auto', padding: '8px 12px', margin: '12px 0 0', color: 'var(--ac-sub)', background: 'var(--ac-line-2)', fontSize: 11, whiteSpace: 'pre-wrap' }}>
          {runtime.log_tail}
        </pre>
      )}

      <div className="ac-eyebrow" style={{ marginTop: 40, marginBottom: 12 }}>{t('settings.speech.models')}</div>
      {!installed ? (
        <div className="ac-hint">{t('settings.speech.modelsHint')}</div>
      ) : (
        <div className="ac-rows">
          {models.map((m) => {
            const downloaded = m.status === 'downloaded'
            const downloading = m.status === 'downloading'
            return (
              <Row
                key={m.name}
                label={
                  <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 10 }}>
                    <span className="ac-mono">{m.name}</span>
                    <span className="ac-mono" style={{ fontSize: 12, color: 'var(--ac-muted)', fontWeight: 400 }}>{m.size}</span>
                    {downloaded && <StatusDot tone="ok" label={t('settings.speech.statusDownloaded')} />}
                  </span>
                }
                hint={
                  <>
                    {m.description}
                    {m.status === 'error' && m.errorMessage && <span style={{ color: 'var(--ac-error)' }}> · {m.errorMessage}</span>}
                  </>
                }
              >
                {downloaded ? (
                  <Popconfirm title={t('settings.speech.deleteModelConfirm', { name: m.name })} onConfirm={() => handleDelete(m.name)} okText={t('common.delete')} cancelText={t('common.cancel')}>
                    <Btn variant="danger" size="sm">{t('common.delete')}</Btn>
                  </Popconfirm>
                ) : downloading ? (
                  <div style={{ width: 160 }}>
                    <ProgressLine percent={m.downloadProgress ?? 0} />
                    <div className="ac-hint" style={{ textAlign: 'right', fontFamily: 'var(--ac-font-mono)' }}>
                      {m.downloadProgress != null ? `${Math.round(m.downloadProgress)}%` : t('settings.speech.downloading')}
                    </div>
                  </div>
                ) : (
                  <Btn size="sm" onClick={() => handleDownload(m.name)}>{t('settings.speech.download')}</Btn>
                )}
              </Row>
            )
          })}
        </div>
      )}
    </>
  )
}

export default SpeechRecognitionConfig
