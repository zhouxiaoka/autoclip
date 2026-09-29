import { t } from '../i18n'
import { useTranslation } from 'react-i18next'
import { forwardRef, useCallback, useEffect, useImperativeHandle, useState } from 'react'
import { message } from 'antd'
import { Btn, Row, Segmented, StatusDot } from '../ui'
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

const SEEDREAM_BASE = 'https://ark.cn-beijing.volces.com/api/v3'
const PRESETS: Record<CoverProvider, { model: string; baseUrl: string }> = {
  openai: { model: 'gpt-image-1', baseUrl: 'https://api.openai.com/v1' },
  seedream: { model: 'doubao-seedream-5-0-260128', baseUrl: SEEDREAM_BASE },
  dashscope: { model: 'wanx2.1-t2i-turbo', baseUrl: '' },
}

export interface CoverSettingsHandle { save: () => Promise<void> }

// 嵌在设置页「AI 分析」里，由页面统一保存；校对标题用视觉理解那一套，不再单独配校对模型
const CoverSettings = forwardRef<CoverSettingsHandle>((_props, ref) => {
  useTranslation()
  const [config, setConfig] = useState<CoverConfigView>(empty)
  const [enabled, setEnabled] = useState(false)
  const [provider, setProvider] = useState<CoverProvider>('openai')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [allowSendFrame, setAllowSendFrame] = useState(false)
  const [loading, setLoading] = useState(true)
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
      setAllowSendFrame(!!cfg.allow_send_frame)
    } catch (err) {
      setError(readApiDetail(err, t("封面生成失败")))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const chooseProvider = (next: CoverProvider) => {
    const prev = PRESETS[provider]
    const preset = PRESETS[next]
    setProvider(next)
    if (!model.trim() || model.trim() === prev.model) setModel(preset.model)
    if (!baseUrl.trim() || baseUrl.trim().replace(/\/+$/, '') === prev.baseUrl.replace(/\/+$/, '')) {
      setBaseUrl(preset.baseUrl)
    }
  }

  useImperativeHandle(ref, () => ({
    save: async () => {
      // 没打开、也没动过：不写封面配置
      if (!enabled && !config.enabled && !apiKey.trim()) return
      const saved = await coverApi.saveConfig({
        enabled,
        provider,
        model: model.trim(),
        api_key: apiKey.trim() || undefined,
        base_url: baseUrl.trim(),
        allow_send_frame: allowSendFrame,
      })
      setConfig(saved)
      setApiKey('')
    },
  }), [enabled, config.enabled, provider, model, apiKey, baseUrl, allowSendFrame])

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
      setAllowSendFrame(false)
      message.success(t("已清除本机保存的封面配置"))
    } catch (err) {
      setError(readApiDetail(err, t("封面生成失败")))
    } finally {
      setClearing(false)
    }
  }

  const preset = PRESETS[provider]

  return (
    <>
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
        {enabled && <>
        <Row label={t("生图提供商")} hint={t("OpenAI 兼容、Seedream（火山方舟）或通义万相。")}>
          <Segmented
            size="sm"
            ariaLabel={t("生图提供商")}
            value={provider}
            onChange={(v) => chooseProvider(v as CoverProvider)}
            options={[
              { value: 'openai', label: t("OpenAI 兼容") },
              { value: 'seedream', label: t("Seedream") },
              { value: 'dashscope', label: t("通义万相") },
            ]}
          />
        </Row>
        <Row wide label={t("生图模型")} hint={provider === 'seedream' ? t("可填方舟接入点 ID（ep-…），或 doubao-seedream-5-0-260128。") : t("例如 gpt-image-1，或 wanx2.1-t2i-turbo。可留空用默认。")}>
          <input className="ac-input ac-input--mono" aria-label={t("生图模型")} value={model} onChange={(e) => setModel(e.target.value)} placeholder={preset.model} />
        </Row>
        <Row
          wide
          label={t("生图密钥")}
          hint={config.source === 'env' ? t("密钥来自环境变量，这里的修改不会覆盖它。")
            : config.key_source === 'text_model' && !apiKey ? t("已复用上面同一家服务的 API Key，不用再填；填写则单独使用。")
            : t("只保存在这台机器上。和上面的模型是同一家服务时可以留空，自动复用。")}
        >
          <input
            className="ac-input ac-input--mono"
            type="password"
            autoComplete="new-password"
            spellCheck={false}
            aria-label={t("生图密钥")}
            placeholder={config.api_key_masked || t("留空复用同一家服务的 Key")}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </Row>
        <Row wide label={t("接口地址")} hint={provider === 'dashscope' ? t("通义万相可留空。") : provider === 'seedream' ? t("默认火山方舟 api/v3。") : t("OpenAI 兼容时填写。通义万相可留空。")}>
          <input className="ac-input ac-input--mono" aria-label={t("接口地址")} value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder={preset.baseUrl} />
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
        <Row label={t("标题校对")} hint={t("生成后用上面「看画面用的模型」读图核对标题文字，对不上会改用本地排版。")} />
        <Row label={t("状态")}>
          {loading ? (
            <StatusDot tone="muted" label={t("还在处理中")} />
          ) : config.configured ? (
            <StatusDot tone="ok" label={config.key_source === 'text_model' ? t("已配置 · 复用模型 Key") : config.api_key_masked ? t("当前密钥 {{key}}", { key: config.api_key_masked }) : t("已配置")} />
          ) : (
            <StatusDot tone="muted" label={t("未配置")} />
          )}
        </Row>
        {config.source === 'file' && (
          <Row label={t("本机封面配置")}>
            <Btn size="sm" variant="text" loading={clearing} onClick={() => void clear()}>{t("清除本机保存的封面配置")}</Btn>
          </Row>
        )}
        </>}
        {error && <p style={{ marginTop: 8, color: 'var(--ac-error)', fontSize: 13 }}>{error}</p>}
      </div>
    </>
  )
})

export default CoverSettings
