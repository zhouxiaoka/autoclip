import { t } from '../i18n'
import { useTranslation } from 'react-i18next'
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Popconfirm, message } from 'antd'
import { speechApi, WhisperRuntimeStatus, WhisperModel } from '../services/api'
import { Btn, ProgressLine, Row, StatusDot } from '../ui'

interface SpeechRecognitionConfigProps {
  config?: Record<string, unknown>
  onConfigChange?: (config: Record<string, unknown>) => void
}

// Whisper 运行时 + 模型管理 — Calm Premium 行式布局（见 DESIGN.md）
const SpeechRecognitionConfig: React.FC<SpeechRecognitionConfigProps> = () => {
  useTranslation()
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
      await speechApi.installRuntime()
      message.info(t("已开始安装"))
      setRuntime((p) => (p ? { ...p, status: 'installing', progress: 5 } : p))
      refresh()
    } catch (e: any) {
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

  if (loading) return <div className="ac-hint">{t("读取 Whisper 状态…")}</div>

  const installed = runtime?.status === 'installed'
  const installing = runtime?.status === 'installing'
  const supported = runtime?.platform_supported !== false

  return (
    <>
      <div className="ac-rows">
        <Row
          top
          label={t("Whisper 运行时")}
          hint={
            !supported ? t("当前平台不支持本地转写。")
              : installed ? t("faster-whisper 已安装{{value1}}。", { value1: runtime?.packages?.length ? `（${runtime.packages.join(', ')}）` : '' })
              : installing ? (runtime?.message || t("正在安装…"))
              : runtime?.status === 'error' ? t("安装出错：{{value1}}", { value1: runtime?.message || '' })
              : t("按需安装，约 200–400 MB（不含 PyTorch）。装好后再选一个模型下载即可。")
          }
        >
          {installed && (
            <>
              <StatusDot tone="ok" label={t("已安装")} />
              <Popconfirm title={t("卸载 Whisper 运行时？已下载的模型不会被删除。")} onConfirm={handleUninstall} okText={t("卸载")} cancelText={t("取消")}>
                <Btn variant="danger" size="sm">{t("卸载")}</Btn>
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
            <Btn variant="cta" size="sm" style={{ height: 32, fontSize: 13, padding: '0 16px' }} onClick={handleInstall} disabled={!supported}>{t("安装")}</Btn>
          )}
          {runtime?.status === 'error' && (
            <Btn size="sm" onClick={handleInstall} disabled={!supported}>{t("重试安装")}</Btn>
          )}
        </Row>
      </div>

      {installing && runtime?.log_tail && (
        <pre className="ac-input ac-input--mono" style={{ height: 'auto', maxHeight: 120, overflow: 'auto', padding: '8px 12px', margin: '12px 0 0', color: 'var(--ac-sub)', background: 'var(--ac-line-2)', fontSize: 11, whiteSpace: 'pre-wrap' }}>
          {runtime.log_tail}
        </pre>
      )}

      <div className="ac-eyebrow" style={{ marginTop: 40, marginBottom: 12 }}>{t("模型")}</div>
      {!installed ? (
        <div className="ac-hint">{t("先安装运行时，再在这里下载模型。")}</div>
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
                    {downloaded && <StatusDot tone="ok" label={t("已下载")} />}
                  </span>
                }
                hint={
                  <>
                    {t(m.description)} {t("· 准确度")}: {t(m.accuracy)} {t("· 速度")}: {t(m.speed)}
                    {m.status === 'error' && m.errorMessage && <span style={{ color: 'var(--ac-error)' }}> · {m.errorMessage}</span>}
                  </>
                }
              >
                {downloaded ? (
                  <Popconfirm title={t("删除模型 {{value1}}？", { value1: m.name })} onConfirm={() => handleDelete(m.name)} okText={t("删除")} cancelText={t("取消")}>
                    <Btn variant="danger" size="sm">{t("删除")}</Btn>
                  </Popconfirm>
                ) : downloading ? (
                  <div style={{ width: 160 }}>
                    <ProgressLine percent={m.downloadProgress ?? 0} />
                    <div className="ac-hint" style={{ textAlign: 'right', fontFamily: 'var(--ac-font-mono)' }}>
                      {m.downloadProgress != null ? `${Math.round(m.downloadProgress)}%` : t("下载中")}
                    </div>
                  </div>
                ) : (
                  <Btn size="sm" onClick={() => handleDownload(m.name)}>{t("下载")}</Btn>
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
