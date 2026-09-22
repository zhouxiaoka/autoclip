import { t } from '../i18n'
import { useTranslation } from 'react-i18next'
import React, { useCallback, useEffect, useState } from 'react'
import { message } from 'antd'
import { Btn, Row, Section, Segmented, StatusDot } from '../ui'
import { readApiDetail } from '../publish/uploadPost'
import { coverApi, type CoverConfigView, type CoverProvider } from '../publish/coverApi'

const empty = (): CoverConfigView => ({
  enabled: false,
  provider: 'openai',
  model: '',
  api_key_masked: '',
  base_url: '',
  ocr_model: '',
  allow_send_frame: false,
  configured: false,
  source: 'none',
})

const CoverSettings: React.FC = () => {
  useTranslation()
  const [config, setConfig] = useState<CoverConfigView>(empty)
  const [enabled, setEnabled] = useState(false)
  const [provider, setProvider] = useState<CoverProvider>('openai')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [ocrModel, setOcrModel] = useState('')
  const [allowSendFrame, setAllowSendFrame] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const cfg = await coverApi.getConfig()
      setConfig(cfg)
      setEnabled(!!cfg.enabled)
      setProvider((cfg.provider as CoverProvider) || 'openai')
      setModel(cfg.model || '')
      setBaseUrl(cfg.base_url || '')
      setOcrModel(cfg.ocr_model || '')
      setAllowSendFrame(!!cfg.allow_send_frame)
    } catch (err) {
      setError(readApiDetail(err, t("封面生成失败")))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const saved = await coverApi.saveConfig({
        enabled,
        provider,
        model: model.trim(),
        api_key: apiKey.trim() || undefined,
        base_url: baseUrl.trim(),
        ocr_model: ocrModel.trim(),
        allow_send_frame: allowSendFrame,
      })
      setConfig(saved)
      setApiKey('')
      message.success(t("封面设置已保存"))
    } catch (err) {
      setError(readApiDetail(err, t("封面生成失败")))
    } finally {
      setSaving(false)
    }
  }

  const clear = async () => {
    setClearing(true)
    setError(null)
    try {
      const cleared = await coverApi.clearConfig()
      setConfig(cleared)
      setEnabled(false)
      setProvider('openai')
      setModel('')
      setApiKey('')
      setBaseUrl('')
      setOcrModel('')
      setAllowSendFrame(false)
      message.success(t("已清除本机保存的封面配置"))
    } catch (err) {
      setError(readApiDetail(err, t("封面生成失败")))
    } finally {
      setClearing(false)
    }
  }

  return (
    <Section
      title={t("封面")}
      description={t("给切片自动设计封面。生图失败时会截帧兜底，不挡住发布。")}
    >
      <div className="ac-rows">
        <Row label={t("自动生成封面")} hint={t("打开后，发布页可以一键生成；B 站投稿优先用设计封面。")}>
          <Segmented
            size="sm"
            ariaLabel={t("自动生成封面")}
            value={enabled ? 'on' : 'off'}
            onChange={(v) => setEnabled(v === 'on')}
            options={[{ value: 'on', label: t("打开") }, { value: 'off', label: t("关闭") }]}
          />
        </Row>
        <Row label={t("生图提供商")} hint={t("OpenAI 兼容接口或通义万相。")}>
          <Segmented
            size="sm"
            ariaLabel={t("生图提供商")}
            value={provider}
            onChange={(v) => setProvider(v as CoverProvider)}
            options={[
              { value: 'openai', label: t("OpenAI 兼容") },
              { value: 'dashscope', label: t("通义万相") },
            ]}
          />
        </Row>
        <Row wide label={t("生图模型")} hint={t("例如 gpt-image-1，或 wanx2.1-t2i-turbo。可留空用默认。")}>
          <input className="ac-input ac-input--mono" aria-label={t("生图模型")} value={model} onChange={(e) => setModel(e.target.value)} placeholder={provider === 'dashscope' ? 'wanx2.1-t2i-turbo' : 'gpt-image-1'} />
        </Row>
        <Row
          wide
          label={t("生图密钥")}
          hint={config.source === 'env' ? t("密钥来自环境变量，这里的修改不会覆盖它。") : t("只保存在这台机器上。")}
        >
          <input
            className="ac-input ac-input--mono"
            type="password"
            autoComplete="new-password"
            spellCheck={false}
            aria-label={t("生图密钥")}
            placeholder={config.api_key_masked || ''}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </Row>
        <Row wide label={t("接口地址")} hint={t("OpenAI 兼容时填写。通义万相可留空。")}>
          <input className="ac-input ac-input--mono" aria-label={t("接口地址")} value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder={provider === 'openai' ? 'https://api.openai.com/v1' : ''} />
        </Row>
        <Row wide label={t("校对模型")} hint={t("多模态模型读图核对标题。可留空。")}>
          <input className="ac-input ac-input--mono" aria-label={t("校对模型")} value={ocrModel} onChange={(e) => setOcrModel(e.target.value)} placeholder={provider === 'dashscope' ? 'qwen-vl-plus' : 'gpt-4o-mini'} />
        </Row>
        <Row
          label={t("允许上传参考帧")}
          hint={t("打开后，会把视频截帧发给生图服务做参考。默认关闭。")}
        >
          <Segmented
            size="sm"
            ariaLabel={t("允许上传参考帧")}
            value={allowSendFrame ? 'on' : 'off'}
            onChange={(v) => setAllowSendFrame(v === 'on')}
            options={[{ value: 'on', label: t("允许") }, { value: 'off', label: t("不允许") }]}
          />
        </Row>
        <Row label={t("状态")}>
          {loading ? (
            <StatusDot tone="muted" label={t("还在处理中")} />
          ) : config.configured ? (
            <StatusDot tone="ok" label={config.api_key_masked ? t("当前密钥 {{key}}", { key: config.api_key_masked }) : t("已配置")} />
          ) : (
            <StatusDot tone="muted" label={t("未配置")} />
          )}
        </Row>
        {error && <p style={{ marginTop: 8, color: 'var(--ac-error)', fontSize: 13 }}>{error}</p>}
        <Row label={t("保存")}>
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn size="sm" variant="cta" loading={saving} onClick={() => void save()}>{t("保存")}</Btn>
            {config.source === 'file' && (
              <Btn size="sm" loading={clearing} onClick={() => void clear()}>{t("清除本机保存的封面配置")}</Btn>
            )}
          </div>
        </Row>
      </div>
    </Section>
  )
}

export default CoverSettings
