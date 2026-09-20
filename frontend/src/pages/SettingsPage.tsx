import React, { useState, useEffect, useMemo } from 'react'
import { Form, Input, Select, Switch, message } from 'antd'
import { useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { settingsApi } from '../services/api'
import SpeechRecognitionConfig from '../components/SpeechRecognitionConfig'
import FeedbackDialog from '../components/FeedbackDialog'
import { isDesktopMode } from '../utils/desktopMode'
import { openExternalLink } from '../utils/externalLinks'
import { trackApiKeyConfigured } from '../analytics/events'
import { isAnalyticsEnabled, setAnalyticsEnabled } from '../analytics/posthog'
import { getRuntimeInfo } from '../analytics/lifecycle'
import { FEEDBACK_FORM_URL, FEEDBACK_ISSUES_URL } from '../analytics/feedback'
import { useTheme } from '../context/ThemeContext'
import { Btn, Icon, Row, Section, Segmented, StatusDot } from '../ui'
import { changeAppLanguage, SupportedLanguage } from '../i18n'

const normalizeBaseUrl = (value: unknown): string =>
  typeof value === 'string' ? value.trim().replace(/\/+$/, '') : ''

// 模型选择框是 mode="tags" 的 Select，用户手动输入后拿到的是数组；后端只接受字符串
const normalizeModelName = (value: unknown): string => {
  if (Array.isArray(value)) return String(value[value.length - 1] ?? '').trim()
  return typeof value === 'string' ? value.trim() : ''
}
const toNumber = (v: unknown, fallback: number): number => {
  const n = typeof v === 'number' ? v : parseFloat(String(v ?? ''))
  return Number.isFinite(n) ? n : fallback
}

type ProviderKey = 'dashscope' | 'openai' | 'gemini' | 'siliconflow' | 'ollama' | 'lmstudio'
type LocalPreset = { baseUrl: string; defaultModel: string; docsUrl: string; app: string }
const PROVIDERS: Record<ProviderKey, { nameKey: string; shortKey: string; hintKey: string; apiKeyField: string; placeholder: string; keyUrl: string; local?: LocalPreset }> = {
  dashscope: { nameKey: 'settings.model.providers.dashscope.name', shortKey: 'settings.model.providers.dashscope.short', hintKey: 'settings.model.providers.dashscope.hint', apiKeyField: 'dashscope_api_key', placeholder: 'sk-…', keyUrl: 'https://dashscope.console.aliyun.com/apiKey' },
  openai: { nameKey: 'settings.model.providers.openai.name', shortKey: 'settings.model.providers.openai.short', hintKey: 'settings.model.providers.openai.hint', apiKeyField: 'openai_api_key', placeholder: 'sk-…', keyUrl: 'https://platform.openai.com/api-keys' },
  gemini: { nameKey: 'settings.model.providers.gemini.name', shortKey: 'settings.model.providers.gemini.short', hintKey: 'settings.model.providers.gemini.hint', apiKeyField: 'gemini_api_key', placeholder: 'AIza…', keyUrl: 'https://aistudio.google.com/apikey' },
  siliconflow: { nameKey: 'settings.model.providers.siliconflow.name', shortKey: 'settings.model.providers.siliconflow.short', hintKey: 'settings.model.providers.siliconflow.hint', apiKeyField: 'siliconflow_api_key', placeholder: 'sk-…', keyUrl: 'https://cloud.siliconflow.cn/account/ak' },
  // 本地预设：底层是 openai 兼容 + base_url，后端 core/local_presets.py 负责还原；无需密钥、不花钱、离线可用
  ollama: { nameKey: 'settings.model.providers.ollama.name', shortKey: 'settings.model.providers.ollama.short', hintKey: 'settings.model.providers.ollama.hint', apiKeyField: 'openai_api_key', placeholder: '', keyUrl: 'https://ollama.com/download', local: { baseUrl: 'http://localhost:11434/v1', defaultModel: 'qwen2.5:7b', docsUrl: 'https://ollama.com/download', app: 'Ollama' } },
  lmstudio: { nameKey: 'settings.model.providers.lmstudio.name', shortKey: 'settings.model.providers.lmstudio.short', hintKey: 'settings.model.providers.lmstudio.hint', apiKeyField: 'openai_api_key', placeholder: '', keyUrl: 'https://lmstudio.ai', local: { baseUrl: 'http://localhost:1234/v1', defaultModel: '', docsUrl: 'https://lmstudio.ai', app: 'LM Studio' } },
}
const isLocalProvider = (p: ProviderKey) => !!PROVIDERS[p]?.local

const getModelGroups = (t: (k: string) => string): Array<{ label: string; models: string[] }> => [
  { label: t('settings.model.modelGroups.qwen'), models: ['qwen-plus', 'qwen-turbo', 'qwen-max', 'qwen-long'] },
  { label: t('settings.model.modelGroups.openai'), models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4.1', 'gpt-4.1-mini'] },
  { label: t('settings.model.modelGroups.gemini'), models: ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-1.5-pro', 'gemini-1.5-flash'] },
  { label: t('settings.model.modelGroups.siliconflow'), models: ['deepseek-ai/DeepSeek-V3', 'deepseek-chat', 'Qwen/Qwen2.5-72B-Instruct'] },
]

const CLOUD_DEFAULT_MODEL: Partial<Record<ProviderKey, string>> = {
  dashscope: 'qwen-plus', openai: 'gpt-4o-mini', gemini: 'gemini-2.5-flash', siliconflow: 'deepseek-ai/DeepSeek-V3',
}

type SectionKey = 'model' | 'speech' | 'app' | 'feedback'
const NAV_KEYS: Array<{ key: SectionKey; labelKey: string }> = [
  { key: 'model', labelKey: 'settings.nav.model' },
  { key: 'speech', labelKey: 'settings.nav.speech' },
  { key: 'app', labelKey: 'settings.nav.app' },
  { key: 'feedback', labelKey: 'settings.nav.feedback' },
]

// Calm Premium settings — left nav + setting rows (see DESIGN.md → App Layer)
const SettingsPage: React.FC = () => {
  const { t } = useTranslation()
  const [form] = Form.useForm()
  const location = useLocation()
  const initialSection = useMemo<SectionKey>(() => {
    const s = new URLSearchParams(location.search).get('section')
    return (NAV_KEYS.find((n) => n.key === s)?.key as SectionKey) || 'model'
  }, [location.search])
  const [active, setActive] = useState<SectionKey>(initialSection)
  const [loading, setLoading] = useState(false)
  const [testing, setTesting] = useState(false)
  const [currentProvider, setCurrentProvider] = useState<any>({})
  const [selectedProvider, setSelectedProvider] = useState<ProviderKey>('dashscope')
  // 本地预设的模型探测：{ reachable, models } —— 让用户从下拉里选，而不是手敲 qwen2.5:7b
  const [localModels, setLocalModels] = useState<{ loading: boolean; reachable: boolean | null; models: string[] }>({ loading: false, reachable: null, models: [] })
  const [analyticsOn, setAnalyticsOn] = useState(isAnalyticsEnabled())
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const runtime = getRuntimeInfo()

  useEffect(() => { loadData() }, [])
  useEffect(() => { setActive(initialSection) }, [initialSection])

  const loadData = async () => {
    try {
      const isDesktop = await isDesktopMode()
      if (isDesktop) {
        const [settings, provider] = await Promise.allSettled([
          settingsApi.getSettings(),
          settingsApi.getCurrentProvider()
        ])
        const settingsData = settings.status === 'fulfilled' ? settings.value : {}
        const providerData = provider.status === 'fulfilled'
          ? provider.value
          : { available: false, provider: 'dashscope', display_name: '阿里通义千问', model: 'qwen-plus' }
        // 以 settings.json 里保存的提供商为准；旧配置没有该字段时退回后端上报的当前提供商
        const providerName = (settingsData.api?.api_provider || providerData.provider || 'dashscope') as ProviderKey
        setCurrentProvider(providerData)
        const savedBaseUrl = settingsData.api?.api_base_url || ''
        const localPreset = PROVIDERS[providerName]?.local
        form.setFieldsValue({
          llm_provider: providerName,
          dashscope_api_key: settingsData.api?.api_keys?.dashscope || '',
          openai_api_key: settingsData.api?.api_keys?.openai || '',
          openai_base_url: localPreset ? '' : savedBaseUrl,
          // 本地预设只在改过默认地址时才把地址填进表单
          local_base_url: localPreset && savedBaseUrl && savedBaseUrl !== localPreset.baseUrl ? savedBaseUrl : '',
          gemini_api_key: settingsData.api?.api_keys?.gemini || '',
          siliconflow_api_key: settingsData.api?.api_keys?.siliconflow || '',
          jimeng_access_key: settingsData.api?.api_keys?.jimeng_access || '',
          jimeng_secret_key: settingsData.api?.api_keys?.jimeng_secret || '',
          model_name: settingsData.api?.api_model || 'qwen-plus',
          chunk_size: settingsData.processing?.processing_chunk_size || 5000,
          min_score_threshold: settingsData.processing?.processing_min_score || 0.7,
          max_clips_per_collection: settingsData.processing?.processing_max_clips || 5
        })
        setSelectedProvider(PROVIDERS[providerName] ? providerName : 'dashscope')
      } else {
        // Web 模式：只展示默认值，不调用桌面 API
        form.setFieldsValue({ llm_provider: 'dashscope', model_name: 'qwen-plus', chunk_size: 5000, min_score_threshold: 0.7, max_clips_per_collection: 5 })
        setSelectedProvider('dashscope')
        setCurrentProvider({ available: false, provider: 'dashscope', display_name: '阿里通义千问', model: 'qwen-plus' })
      }
    } catch (err) {
      console.error('加载数据失败:', err)
    }
  }

  const handleSave = async (values: any) => {
    try {
      setLoading(true)
      const isDesktop = await isDesktopMode()
      if (!isDesktop) {
        message.info(t('settings.model.webModeNotice'))
        return
      }
      // 先读现有配置，避免清空其它 provider 已保存的 key
      let existing: any = null
      try { existing = await settingsApi.getSettings() } catch (err) { console.warn('获取现有配置失败:', err) }
      const keys = existing?.api?.api_keys || {}
      const provider = (values.llm_provider || selectedProvider) as ProviderKey

      await settingsApi.updateSettings({
        basic: { app_name: 'AutoClip Desktop', app_version: runtime.version !== 'unknown' ? runtime.version : '1.0.0', debug_mode: false, auto_start: true },
        service: { host: '127.0.0.1', port: 8000, max_memory_usage: 2048 },
        api: {
          api_keys: {
            dashscope: values.dashscope_api_key || keys.dashscope || '',
            openai: values.openai_api_key || keys.openai || '',
            gemini: values.gemini_api_key || keys.gemini || '',
            siliconflow: values.siliconflow_api_key || keys.siliconflow || '',
            jimeng_access: values.jimeng_access_key || keys.jimeng_access || '',
            jimeng_secret: values.jimeng_secret_key || keys.jimeng_secret || ''
          },
          api_provider: provider,
          api_base_url: provider === 'openai'
            ? normalizeBaseUrl(values.openai_base_url)
            : isLocalProvider(provider) ? normalizeBaseUrl(values.local_base_url) : '',
          api_model: normalizeModelName(values.model_name) || 'qwen-plus',
          api_max_tokens: 4096,
          api_timeout: 30
        },
        processing: {
          processing_chunk_size: toNumber(values.chunk_size, 5000),
          processing_min_score: toNumber(values.min_score_threshold, 0.7),
          processing_max_clips: toNumber(values.max_clips_per_collection, 5),
          processing_max_retries: 3
        },
        logs: { log_level: 'INFO', log_retention_days: 7 }
        // paths 由后端根据实际数据目录决定，前端不下发
      })
      message.success(t('common.saved'))
      trackApiKeyConfigured({ provider, hasKey: isLocalProvider(provider) || !!values[PROVIDERS[provider].apiKeyField] })
      await loadData()
    } catch (err: any) {
      message.error(t('common.saveFailed') + ': ' + (err.message || t('common.unknownError')))
    } finally {
      setLoading(false)
    }
  }

  const handleTest = async () => {
    const cfg = PROVIDERS[selectedProvider]
    const local = isLocalProvider(selectedProvider)
    const apiKey: string = local ? '' : (form.getFieldValue(cfg.apiKeyField) || '')
    const baseUrl = selectedProvider === 'openai'
      ? normalizeBaseUrl(form.getFieldValue('openai_base_url'))
      : local ? (normalizeBaseUrl(form.getFieldValue('local_base_url')) || cfg.local!.baseUrl) : ''
    const modelName = normalizeModelName(form.getFieldValue('model_name'))
    if (local && !modelName) {
      message.error(t('settings.model.selectModelFirst'))
      return
    }
    // 自建兼容服务（Ollama / vLLM 等）通常不需要 key，有地址就能测
    if (!apiKey.trim() && !baseUrl) {
      message.error(t('settings.model.enterApiKeyFirst'))
      return
    }
    try {
      setTesting(true)
      const r = await settingsApi.testApiKey(selectedProvider, apiKey, { baseUrl: baseUrl || undefined, model: modelName || undefined })
      if (r.success) message.success(t('settings.model.connectionSuccess'))
      else message.error(t('settings.model.connectionFailed') + (r.error || t('common.unknownError')))
    } catch (err: any) {
      message.error(t('settings.model.connectionFailed') + (err.message || t('common.unknownError')))
    } finally {
      setTesting(false)
    }
  }

  const detectLocalModels = async (p: ProviderKey, baseUrl?: string) => {
    const preset = PROVIDERS[p]?.local
    if (!preset) return
    setLocalModels((s) => ({ ...s, loading: true }))
    try {
      const r = await settingsApi.listCompatibleModels({ provider: p, baseUrl: normalizeBaseUrl(baseUrl) || undefined })
      setLocalModels({ loading: false, reachable: r.reachable, models: r.models || [] })
      // 探测到模型且当前没选 / 选的不在列表里 → 帮用户选一个（优先预设默认）
      const current = normalizeModelName(form.getFieldValue('model_name'))
      if (r.reachable && r.models.length && (!current || !r.models.includes(current))) {
        form.setFieldsValue({ model_name: r.models.includes(preset.defaultModel) ? preset.defaultModel : r.models[0] })
      }
    } catch {
      setLocalModels({ loading: false, reachable: false, models: [] })
    }
  }

  const handleProviderChange = (p: ProviderKey) => {
    const prev = selectedProvider
    setSelectedProvider(p)
    form.setFieldsValue({ llm_provider: p })
    const preset = PROVIDERS[p]?.local
    const current = normalizeModelName(form.getFieldValue('model_name'))
    const modelGroups = getModelGroups(t)
    if (preset) {
      // 从云端切到本地时，qwen-plus 这类云端模型名对本地服务没意义
      if (!current || modelGroups.some((g) => g.models.includes(current))) {
        form.setFieldsValue({ model_name: preset.defaultModel || undefined })
      }
      void detectLocalModels(p, form.getFieldValue('local_base_url'))
    } else if (isLocalProvider(prev) || !current) {
      // 从本地切回云端：qwen2.5:7b 这类本地模型名对云端没意义，给该提供商一个常用默认
      form.setFieldsValue({ model_name: CLOUD_DEFAULT_MODEL[p] })
    }
  }

  // 打开设置页时若已是本地预设，顺手探测一次
  useEffect(() => {
    if (isLocalProvider(selectedProvider)) void detectLocalModels(selectedProvider, form.getFieldValue('local_base_url'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProvider])

  const openaiBaseUrl = Form.useWatch('openai_base_url', form)
  const usingCustomEndpoint = selectedProvider === 'openai' && !!normalizeBaseUrl(openaiBaseUrl)
  const cfg = PROVIDERS[selectedProvider]
  const localCfg = cfg.local

  return (
    <div className="ac-page">
      <header>
        <h1 className="ac-title" style={{ marginTop: 0 }}>{t('settings.pageTitle')}</h1>
        <div className="ac-meta">
          <span className="ac-mono">{runtime.version !== 'unknown' ? `v${runtime.version}` : 'dev'}</span>
          <span className="dot" />
          <span className="ac-mono">{runtime.os}/{runtime.arch}</span>
          {currentProvider?.available && (
            <>
              <span className="dot" />
              <span>{t('settings.currentModel')} <span className="ac-mono">{currentProvider.provider} · {currentProvider.model}</span></span>
            </>
          )}
        </div>
      </header>

      <div className="ac-settings" style={{ marginTop: 36 }}>
        <nav className="ac-settings-nav" aria-label={t('settings.pageTitle')}>
          {NAV_KEYS.map((n) => (
            <button key={n.key} aria-current={active === n.key} onClick={() => setActive(n.key)}>{t(n.labelKey)}</button>
          ))}
        </nav>

        <div className="ac-settings-body">
          {/* ---------------- 模型 ---------------- */}
          {active === 'model' && (
            <Section title={t('settings.model.sectionTitle')} description={t('settings.model.sectionDesc')}>
              <Form
                form={form}
                layout="vertical"
                onFinish={handleSave}
                requiredMark={false}
                initialValues={{ llm_provider: 'dashscope', model_name: 'qwen-plus', chunk_size: 5000, min_score_threshold: 0.7, max_clips_per_collection: 5 }}
              >
                <Form.Item name="llm_provider" hidden><Input /></Form.Item>
                <div className="ac-rows">
                  <Row label={t('settings.model.provider')} hint={t(cfg.hintKey)} stack>
                    <Segmented
                      size="sm"
                      ariaLabel={t('settings.model.provider')}
                      value={selectedProvider}
                      onChange={handleProviderChange}
                      options={(Object.keys(PROVIDERS) as ProviderKey[]).map((k) => ({ value: k, label: t(PROVIDERS[k].shortKey) }))}
                    />
                  </Row>

                  {localCfg && (
                    <Row
                      wide
                      label={t('settings.model.serviceUrl')}
                      hint={<>{t('settings.model.serviceUrlHint', { baseUrl: localCfg.baseUrl, app: localCfg.app })}{' '}<a href={localCfg.docsUrl} onClick={(e) => { e.preventDefault(); openExternalLink(localCfg.docsUrl) }} style={{ color: 'var(--ac-accent)' }}>{localCfg.app}</a></>}
                    >
                      <Form.Item
                        name="local_base_url"
                        style={{ width: '100%' }}
                        rules={[{
                          validator: (_, value) => {
                            const url = normalizeBaseUrl(value)
                            if (!url || /^https?:\/\/\S+$/.test(url)) return Promise.resolve()
                            return Promise.reject(new Error(t('settings.model.urlFormatError')))
                          },
                        }]}
                      >
                        <Input
                          placeholder={localCfg.baseUrl}
                          allowClear
                          className="ac-mono"
                          onBlur={(e) => void detectLocalModels(selectedProvider, e.target.value)}
                        />
                      </Form.Item>
                    </Row>
                  )}

                  {selectedProvider === 'openai' && (
                    <Row
                      wide
                      label={t('settings.model.apiUrl')}
                      hint={<>{t('settings.model.apiUrlHint')}</>}
                    >
                      <Form.Item
                        name="openai_base_url"
                        style={{ width: '100%' }}
                        rules={[{
                          validator: (_, value) => {
                            const url = normalizeBaseUrl(value)
                            if (!url || /^https?:\/\/\S+$/.test(url)) return Promise.resolve()
                            return Promise.reject(new Error(t('settings.model.urlFormatError')))
                          },
                        }]}
                      >
                        <Input placeholder="https://api.openai.com/v1" allowClear className="ac-mono" />
                      </Form.Item>
                    </Row>
                  )}

                  {!localCfg && <Row
                    wide
                    label={t('settings.model.apiKey')}
                    hint={usingCustomEndpoint
                      ? t('settings.model.apiKeyCustomHint')
                      : <>{t('settings.model.apiKeyConsole', { name: t(cfg.nameKey) })}{' '}<a href={cfg.keyUrl} onClick={(e) => { e.preventDefault(); openExternalLink(cfg.keyUrl) }} style={{ color: 'var(--ac-accent)' }}>{t(cfg.nameKey)}</a></>}
                  >
                    <Form.Item
                      name={cfg.apiKeyField}
                      style={{ width: '100%' }}
                      rules={usingCustomEndpoint ? [] : [
                        { required: true, message: t('settings.model.apiKeyRequired') },
                        { min: 10, message: t('settings.model.apiKeyMinLength') }
                      ]}
                    >
                      <Input.Password placeholder={cfg.placeholder} className="ac-mono" />
                    </Form.Item>
                  </Row>}

                  <Row
                    wide
                    label={t('settings.model.model')}
                    hint={localCfg
                      ? (localModels.loading
                          ? t('settings.model.detectingLocal')
                          : localModels.reachable
                            ? <>{t('settings.model.detectedLocal', { count: localModels.models.length })}{' '}<a onClick={() => void detectLocalModels(selectedProvider, form.getFieldValue('local_base_url'))} style={{ color: 'var(--ac-accent)', cursor: 'pointer' }}>{t('settings.model.refresh')}</a></>
                            : localModels.reachable === false
                              ? <>{t('settings.model.notReachable', { app: localCfg.app, pullNotice: localCfg.defaultModel ? ` (ollama pull ${localCfg.defaultModel})` : '' })}{' '}<a onClick={() => void detectLocalModels(selectedProvider, form.getFieldValue('local_base_url'))} style={{ color: 'var(--ac-accent)', cursor: 'pointer' }}>{t('settings.model.refresh')}</a></>
                              : t('settings.model.localSelectHint'))
                      : usingCustomEndpoint
                        ? t('settings.model.customEndpointHint')
                        : t('settings.model.directInputHint')}
                  >
                    <Form.Item name="model_name" style={{ width: '100%' }} rules={[{ required: true, message: t('settings.model.modelRequired') }]}>
                      <Select
                        placeholder={localCfg ? (localCfg.defaultModel || t('settings.model.modelPlaceholder')) : 'qwen-plus'}
                        showSearch
                        allowClear
                        mode="tags"
                        maxCount={1}
                        loading={localCfg ? localModels.loading : false}
                        className="ac-mono"
                        options={(localCfg
                          ? localModels.models.map((m) => ({ value: m, label: m }))
                          : getModelGroups(t).map((g) => ({ label: g.label, options: g.models.map((m) => ({ value: m, label: m })) }))) as any}
                      />
                    </Form.Item>
                  </Row>

                  <Row label={t('settings.model.connectionTest')} hint={localCfg ? t('settings.model.connectionTestHintLocal') : t('settings.model.connectionTestHintCloud')}>
                    <Btn size="sm" loading={testing} onClick={handleTest}>{t('settings.model.testConnection')}</Btn>
                  </Row>
                </div>

                <div className="ac-eyebrow" style={{ marginTop: 40, marginBottom: 12 }}>{t('settings.model.sliceParams')}</div>
                <div className="ac-rows">
                  <Row label={t('settings.model.chunkSize')} hint={t('settings.model.chunkSizeHint')}>
                    <Form.Item name="chunk_size">
                      <input className="ac-input ac-input--mono" type="number" min={1000} step={500} style={{ width: 120, textAlign: 'right' }} />
                    </Form.Item>
                    <span className="ac-unit">{t('common.characters')}</span>
                  </Row>
                  <Row label={t('settings.model.minScore')} hint={t('settings.model.minScoreHint')}>
                    <Form.Item name="min_score_threshold">
                      <input className="ac-input ac-input--mono" type="number" min={0} max={1} step={0.05} style={{ width: 120, textAlign: 'right' }} />
                    </Form.Item>
                    <span className="ac-unit" />
                  </Row>
                  <Row label={t('settings.model.maxClips')} hint={t('settings.model.maxClipsHint')}>
                    <Form.Item name="max_clips_per_collection">
                      <input className="ac-input ac-input--mono" type="number" min={1} max={20} style={{ width: 120, textAlign: 'right' }} />
                    </Form.Item>
                    <span className="ac-unit">{t('common.items')}</span>
                  </Row>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 12, marginTop: 28 }}>
                  {currentProvider?.available && (
                    <StatusDot tone="ok" label={<>{t('settings.model.configured')} <span className="ac-mono">{currentProvider.display_name} · {currentProvider.model}</span></>} />
                  )}
                  <Btn variant="cta" loading={loading} onClick={() => form.submit()}>{t('common.save')}</Btn>
                </div>
              </Form>
            </Section>
          )}

          {/* ---------------- 转写 ---------------- */}
          {active === 'speech' && (
            <Section
              title={t('settings.speech.sectionTitle')}
              description={t('settings.speech.sectionDesc')}
            >
              <SpeechRecognitionConfig />
            </Section>
          )}

          {/* ---------------- 应用 ---------------- */}
          {active === 'app' && (
            <AppSection analyticsOn={analyticsOn} onAnalyticsChange={(on) => { setAnalyticsEnabled(on); setAnalyticsOn(on) }} />
          )}

          {/* ---------------- 反馈 ---------------- */}
          {active === 'feedback' && (
            <Section title={t('settings.feedback.sectionTitle')} description={t('settings.feedback.sectionDesc')}>
              <div className="ac-rows">
                <Row label={t('settings.feedback.sendFeedback')} hint={t('settings.feedback.sendFeedbackHint')}>
                  <Btn variant="cta" size="sm" style={{ height: 32, fontSize: 13, padding: '0 16px' }} onClick={() => setFeedbackOpen(true)}>
                    <Icon.Chat size={13} /> {t('settings.feedback.writeFeedback')}
                  </Btn>
                </Row>
                <Row label={t('settings.feedback.feedbackForm')} hint={t('settings.feedback.feedbackFormHint')}>
                  <Btn size="sm" onClick={() => openExternalLink(FEEDBACK_FORM_URL)}>{t('settings.feedback.openForm')} <Icon.External size={12} /></Btn>
                </Row>
                <Row label={t('settings.feedback.github')} hint={t('settings.feedback.githubHint')}>
                  <Btn size="sm" onClick={() => openExternalLink(FEEDBACK_ISSUES_URL)}>{t('settings.feedback.newIssue')} <Icon.External size={12} /></Btn>
                </Row>
                <Row label={t('settings.feedback.knownIssues')} hint={t('settings.feedback.knownIssuesHint')}>
                  <Btn variant="text" size="sm" onClick={() => openExternalLink('https://github.com/zhouxiaoka/autoclip/issues/96')}>#96 <Icon.External size={12} /></Btn>
                </Row>
              </div>
            </Section>
          )}
        </div>
      </div>

      <FeedbackDialog open={feedbackOpen} onClose={() => setFeedbackOpen(false)} context={{ source: 'settings' }} />
    </div>
  )
}

/* ---------------- 应用 ---------------- */
const AppSection: React.FC<{ analyticsOn: boolean; onAnalyticsChange: (on: boolean) => void }> = ({ analyticsOn, onAnalyticsChange }) => {
  const { t, i18n } = useTranslation()
  const { theme, setTheme } = useTheme()
  const [autostart, setAutostart] = useState(false)
  const [busy, setBusy] = useState(false)
  const [desktop, setDesktop] = useState(false)

  useEffect(() => {
    (async () => {
      try {
        const isDesktop = await isDesktopMode()
        setDesktop(isDesktop)
        if (isDesktop) {
          const { invoke } = await import('@tauri-apps/api/core')
          setAutostart(Boolean(await invoke('is_autostart_enabled')))
        }
      } catch (err) {
        console.error('检查自动启动状态失败:', err)
      }
    })()
  }, [])

  const toggleAutostart = async (enabled: boolean) => {
    if (!desktop) { message.error(t('common.desktopOnly')); return }
    setBusy(true)
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      await invoke(enabled ? 'enable_autostart' : 'disable_autostart')
      setAutostart(enabled)
    } catch (err) {
      console.error('切换自动启动状态失败:', err)
      message.error(`${t('common.error')}: ${err}`)
    } finally {
      setBusy(false)
    }
  }

  const handleLanguageChange = (newLang: SupportedLanguage) => {
    changeAppLanguage(newLang)
  }

  const currentLang = i18n.language?.startsWith('en') ? 'en' : 'zh'

  return (
    <Section title={t('settings.app.sectionTitle')} description={t('settings.app.sectionDesc')}>
      <div className="ac-rows">
        <Row label={t('settings.app.appearance')} hint={t('settings.app.appearanceHint')}>
          <Segmented size="sm" ariaLabel={t('settings.app.appearance')} value={theme} onChange={setTheme} options={[{ value: 'light', label: t('settings.app.light') }, { value: 'dark', label: t('settings.app.dark') }]} />
        </Row>
        <Row label="Language / 界面语言" hint={t('settings.app.languageHint')}>
          <Select
            value={currentLang}
            onChange={handleLanguageChange}
            style={{ width: 260 }}
            options={[
              { value: 'zh', label: '简体中文 (Simplified Chinese)' },
              { value: 'en', label: 'English (English)' }
            ]}
          />
        </Row>
        <Row label={t('settings.app.autostart')} hint={t('settings.app.autostartHint')}>
          <Switch checked={autostart} onChange={toggleAutostart} loading={busy} disabled={!desktop} />
        </Row>
        <Row label={t('settings.app.analytics')} hint={t('settings.app.analyticsHint')}>
          <Switch checked={analyticsOn} onChange={onAnalyticsChange} />
        </Row>
        <Row label={t('settings.app.bilibiliAccount')} hint={t('settings.app.bilibiliAccountHint')}>
          <span className="ac-hint" style={{ margin: 0 }}>{t('common.comingSoon')}</span>
        </Row>
      </div>
    </Section>
  )
}

export default SettingsPage
