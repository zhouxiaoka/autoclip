import React, { useCallback, useEffect, useRef, useState } from 'react'
import {
  Alert, Button, Card, Progress, Tag, Space, Typography, message, List, Popconfirm, Spin, Tooltip,
} from 'antd'
import {
  DownloadOutlined, DeleteOutlined, CheckCircleFilled, ReloadOutlined, ThunderboltOutlined,
} from '@ant-design/icons'
import { speechApi, WhisperRuntimeStatus, WhisperModel } from '../services/api'

const { Text, Paragraph } = Typography

interface SpeechRecognitionConfigProps {
  config?: Record<string, unknown>
  onConfigChange?: (config: Record<string, unknown>) => void
}

const accuracyColor: Record<string, string> = {
  最高: 'green', 高: 'green', 较好: 'blue', 中等: 'gold', 较低: 'default',
}

const SpeechRecognitionConfig: React.FC<SpeechRecognitionConfigProps> = () => {
  const [runtime, setRuntime] = useState<WhisperRuntimeStatus | null>(null)
  const [models, setModels] = useState<WhisperModel[]>([])
  const [loading, setLoading] = useState(true)
  const timer = useRef<number | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [rt, ms] = await Promise.all([speechApi.getRuntimeStatus(), speechApi.getModels()])
      setRuntime(rt)
      setModels(Array.isArray(ms) ? ms : [])
    } catch (e) {
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
    const interval = needsFastPoll(runtime, models) ? 2000 : 15000
    timer.current = window.setInterval(refresh, interval)
    return () => { if (timer.current) window.clearInterval(timer.current) }
  }, [runtime, models, refresh])

  const handleInstall = async () => {
    try {
      const r = await speechApi.installRuntime()
      message.info(r.message || '已开始安装')
      setRuntime((p) => (p ? { ...p, status: 'installing', progress: 5 } : p))
      refresh()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '安装失败')
    }
  }

  const handleUninstall = async () => {
    try {
      const r = await speechApi.uninstallRuntime()
      message.success(r.message || '已卸载')
      refresh()
    } catch (e: any) {
      message.error('卸载失败')
    }
  }

  const handleDownload = async (model: string) => {
    try {
      await speechApi.downloadModel(model)
      message.info(`开始下载模型 ${model}`)
      setModels((prev) => prev.map((m) => (m.name === model ? { ...m, status: 'downloading' } : m)))
      refresh()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '下载失败')
    }
  }

  const handleDelete = async (model: string) => {
    try {
      await speechApi.deleteModel(model)
      message.success(`已删除模型 ${model}`)
      refresh()
    } catch (e) {
      message.error('删除失败')
    }
  }

  if (loading) return <Spin />

  const installed = runtime?.status === 'installed'
  const installing = runtime?.status === 'installing'
  const supported = runtime?.platform_supported !== false

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message="When do I need Whisper?"
        description="If the video already has captions (for example Bilibili AI captions), AutoClip uses those. Whisper is only needed when there are no captions. Install it only if you want."
      />

      {!supported && (
        <Alert type="warning" showIcon message="Not supported on this platform"
          description="mlx-whisper only runs on Apple Silicon (M-series) Macs." />
      )}

      {/* 运行时 */}
      <Card size="small" title={<Space><ThunderboltOutlined />Whisper runtime</Space>}>
        {installed && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Space>
              <CheckCircleFilled style={{ color: '#52c41a' }} />
              <Text strong>Installed</Text>
              <Text type="secondary">（{(runtime?.packages || []).join(', ')}）</Text>
            </Space>
            <Popconfirm title="Uninstall Whisper runtime? Downloaded models will be kept." onConfirm={handleUninstall} okText="Uninstall" cancelText="Cancel">
              <Button danger size="small" icon={<DeleteOutlined />}>Uninstall runtime</Button>
            </Popconfirm>
          </Space>
        )}

        {installing && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text>Installing… {runtime?.message}</Text>
            <Progress percent={runtime?.progress ?? 5} status="active" />
            {runtime?.log_tail && (
              <pre style={{ maxHeight: 120, overflow: 'auto', background: '#1a1a1a', color: '#bbb', padding: 8, fontSize: 11, borderRadius: 4, margin: 0 }}>
                {runtime.log_tail}
              </pre>
            )}
          </Space>
        )}

        {runtime?.status === 'not_installed' && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Paragraph type="secondary" style={{ marginBottom: 8 }}>
              Not installed. This downloads the faster-whisper runtime (~200–400MB, no PyTorch). Then download a model to use it.
            </Paragraph>
            <Button type="primary" icon={<DownloadOutlined />} onClick={handleInstall} disabled={!supported}>
              Install Whisper
            </Button>
          </Space>
        )}

        {runtime?.status === 'error' && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Alert type="error" showIcon message="Install failed" description={runtime?.message} />
            <Button icon={<ReloadOutlined />} onClick={handleInstall} disabled={!supported}>Retry install</Button>
          </Space>
        )}
      </Card>

      {/* 模型 */}
      <Card size="small" title="Whisper models">
        {!installed && (
          <Text type="secondary">Install the Whisper runtime first, then download a model here.</Text>
        )}
        {installed && (
          <List
            dataSource={models}
            renderItem={(m) => {
              const downloaded = m.status === 'downloaded'
              const downloading = m.status === 'downloading'
              return (
                <List.Item
                  actions={[
                    downloaded ? (
                      <Popconfirm title={`Delete model ${m.name}?`} onConfirm={() => handleDelete(m.name)} okText="Delete" cancelText="Cancel">
                        <Button size="small" danger icon={<DeleteOutlined />}>Delete</Button>
                      </Popconfirm>
                    ) : downloading ? (
                      <Button size="small" loading disabled>Downloading</Button>
                    ) : (
                      <Button size="small" type="primary" icon={<DownloadOutlined />} onClick={() => handleDownload(m.name)}>
                        Download
                      </Button>
                    ),
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space>
                        <Text strong>{m.name}</Text>
                        <Text type="secondary">{m.size}</Text>
                        {downloaded && <Tag color="green">Downloaded</Tag>}
                        <Tag color={accuracyColor[m.accuracy] || 'default'}>Accuracy {m.accuracy}</Tag>
                        <Tooltip title="Speed"><Tag>{m.speed}</Tag></Tooltip>
                      </Space>
                    }
                    description={
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <Text type="secondary">{m.description}</Text>
                        {downloading && <Progress percent={m.downloadProgress ?? undefined} status="active" />}
                        {m.status === 'error' && m.errorMessage && <Text type="danger">{m.errorMessage}</Text>}
                      </Space>
                    }
                  />
                </List.Item>
              )
            }}
          />
        )}
      </Card>
    </Space>
  )
}

export default SpeechRecognitionConfig
