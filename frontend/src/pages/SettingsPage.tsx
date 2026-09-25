import { t } from '../i18n'
import { useTranslation } from 'react-i18next'
import React, { useState, useEffect, useMemo } from 'react'
import { Form, Input, Select, Switch, message } from 'antd'
import { useLocation } from 'react-router-dom'
import { settingsApi } from '../services/api'
import SpeechRecognitionConfig from '../components/SpeechRecognitionConfig'
import FeedbackDialog from '../components/FeedbackDialog'
import PublishSettings from '../components/PublishSettings'
import CoverSettings from '../components/CoverSettings'
import { isDesktopMode } from '../utils/desktopMode'
import { openExternalLink } from '../utils/externalLinks'
import { trackApiKeyConfigured } from '../analytics/events'
import { isAnalyticsEnabled, setAnalyticsEnabled } from '../analytics/posthog'
import { getRuntimeInfo } from '../analytics/lifecycle'
import { isCrashReportsEnabled, setCrashReportsEnabled } from '../desktop/sentry'
import { getAppVersion } from '../desktop/updater'
import { useAppUpdate } from '../desktop/UpdatePrompt'
import { FEEDBACK_DISCUSSIONS_URL, FEEDBACK_ISSUES_URL } from '../analytics/feedback'
import { useTheme } from '../context/ThemeContext'
import { Btn, Icon, Row, Section, Segmented, StatusDot } from '../ui'

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

type ProviderKey = 'dashscope' | 'openai' | 'gemini' | 'deepseek' | 'seed' | 'kimi' | 'glm' | 'grok' | 'ollama' | 'lmstudio'
type LocalPreset = { baseUrl: string; defaultModel: string; docsUrl: string; app: string }
type CloudPreset = { baseUrl: string; defaultModel: string }
const PROVIDERS: Record<ProviderKey, { name: string; short: string; hint: string; apiKeyField: string; placeholder: string; keyUrl: string; local?: LocalPreset; cloud?: CloudPreset }> = {
  dashscope: { get name() { return t("阿里通义千问") }, get short() { return t("通义千问") }, get hint() { return t("阿里云 DashScope。国内直连，qwen-plus 性价比高。") }, apiKeyField: 'dashscope_api_key', placeholder: 'sk-…', keyUrl: 'https://dashscope.console.aliyun.com/apiKey' },
  openai: { get name() { return t("OpenAI / 兼容接口") }, get short() { return t("OpenAI 兼容") }, get hint() { return t("OpenAI，或任何兼容接口：OpenRouter、vLLM。") }, apiKeyField: 'openai_api_key', get placeholder() { return t("sk-…（自建服务可留空）") }, keyUrl: 'https://platform.openai.com/api-keys' },
  gemini: { name: 'Google Gemini', short: 'Gemini', get hint() { return t("Google AI Studio 的 Gemini 系列。") }, apiKeyField: 'gemini_api_key', placeholder: 'AIza…', keyUrl: 'https://aistudio.google.com/apikey' },
  deepseek: { name: 'DeepSeek', short: 'DeepSeek', get hint() { return t("DeepSeek 官方。国内直连，deepseek-flash 是当前 V4.1。") }, apiKeyField: 'deepseek_api_key', placeholder: 'sk-…', keyUrl: 'https://platform.deepseek.com/api_keys', cloud: { baseUrl: 'https://api.deepseek.com', defaultModel: 'deepseek-flash' } },
  seed: { name: 'Seed', short: 'Seed', get hint() { return t("火山方舟 Seed。国内直连，豆包 Seed 2.1 系列。") }, apiKeyField: 'seed_api_key', placeholder: '…', keyUrl: 'https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey', cloud: { baseUrl: 'https://ark.cn-beijing.volces.com/api/v3', defaultModel: 'doubao-seed-2-1-lite-260915' } },
  kimi: { name: 'Kimi', short: 'Kimi', get hint() { return t("月之暗面 Kimi。国内直连，适合长字幕分析。") }, apiKeyField: 'kimi_api_key', placeholder: 'sk-…', keyUrl: 'https://platform.moonshot.cn/console/api-keys', cloud: { baseUrl: 'https://api.moonshot.cn/v1', defaultModel: 'kimi-k2.6' } },
  glm: { get name() { return t("智谱 GLM") }, get short() { return 'GLM' }, get hint() { return t("智谱开放平台。国内直连，glm-5.3 是当前旗舰。") }, apiKeyField: 'glm_api_key', placeholder: '…', keyUrl: 'https://open.bigmodel.cn/usercenter/apikeys', cloud: { baseUrl: 'https://open.bigmodel.cn/api/paas/v4', defaultModel: 'glm-5.3' } },
  grok: { name: 'Grok', short: 'Grok', get hint() { return t("xAI Grok。需要 xAI 账号。") }, apiKeyField: 'grok_api_key', placeholder: 'xai-…', keyUrl: 'https://console.x.ai', cloud: { baseUrl: 'https://api.x.ai/v1', defaultModel: 'grok-4.6' } },
  // 本地预设：底层是 openai 兼容 + base_url，后端 core/local_presets.py 负责还原；无需密钥、不花钱、离线可用
  ollama: { name: 'Ollama', short: 'Ollama', get hint() { return t("本机运行的 Ollama，免费、离线。推荐 ollama pull qwen2.5:7b。") }, apiKeyField: 'openai_api_key', placeholder: '', keyUrl: 'https://ollama.com/download', local: { baseUrl: 'http://localhost:11434/v1', defaultModel: 'qwen2.5:7b', docsUrl: 'https://ollama.com/download', app: 'Ollama' } },
  lmstudio: { name: 'LM Studio', short: 'LM Studio', get hint() { return t("本机 LM Studio 的 Local Server，免费、离线。在 LM Studio 里加载模型并启动服务。") }, apiKeyField: 'openai_api_key', placeholder: '', keyUrl: 'https://lmstudio.ai', local: { baseUrl: 'http://localhost:1234/v1', defaultModel: '', docsUrl: 'https://lmstudio.ai', app: 'LM Studio' } },
}
const isLocalProvider = (p: ProviderKey) => !!PROVIDERS[p]?.local
const isCloudPreset = (p: ProviderKey) => !!PROVIDERS[p]?.cloud

// 通义千问国际站（alibabacloud.com 开通的 key 只能打这个域名，#45）；后端据 base_url 自动走兼容模式
const DASHSCOPE_INTL_BASE_URL = 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1'
type DashscopeRegion = 'cn' | 'intl'

// 后端 /available-models 失败时的兜底；与 backend/core/model_catalog.py 对齐
const FALLBACK_CATALOG: Record<string, string[]> = {
  dashscope: ['qwen3.8-max', 'qwen3.8-flash', 'qwen3.7-plus', 'qwen-plus', 'qwen-plus-latest', 'qwen-max', 'qwen-max-latest', 'qwen-flash'],
  openai: ['gpt-5.6-sol', 'gpt-5.6-terra', 'gpt-5.6-luna', 'gpt-5.4', 'gpt-5.4-mini', 'gpt-5', 'gpt-5-mini', 'gpt-5-nano'],
  gemini: ['gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-pro-preview', 'gemini-3-flash-preview', 'gemini-2.5-flash'],
  deepseek: ['deepseek-flash', 'deepseek-v4-pro'],
  seed: ['doubao-seed-2-1-lite-260915', 'doubao-seed-2-1-pro-260915', 'doubao-seed-2-1-turbo-260628', 'doubao-seed-evolving'],
  kimi: ['kimi-k3', 'kimi-k2.6', 'kimi-k2.5', 'kimi-k2.7-code'],
  glm: ['glm-5.3', 'glm-5.2', 'glm-4.7'],
  grok: ['grok-4.6', 'grok-4.5', 'grok-4.3'],
}
const PROVIDER_GROUP_ORDER: ProviderKey[] = ['dashscope', 'openai', 'gemini', 'deepseek', 'seed', 'kimi', 'glm', 'grok']
const providerGroupLabel = (key: string) => ({
  dashscope: t("通义千问"), openai: 'OpenAI', gemini: 'Gemini', deepseek: 'DeepSeek',
  seed: 'Seed', kimi: 'Kimi', glm: 'GLM', grok: 'Grok',
} as Record<string, string>)[key] || key
const knownCloudModels = (catalog: Record<string, string[]>, extra: string[] = []) =>
  new Set([...Object.values(catalog).flat(), ...extra])

const cloudModelOptions = (
  provider: ProviderKey,
  state: { source: 'catalog' | 'live'; models: string[]; catalog: Record<string, string[]> },
) => {
  const catalog = Object.keys(state.catalog).length ? state.catalog : FALLBACK_CATALOG
  const current = state.source === 'live' && state.models.length
    ? state.models
    : (catalog[provider] || FALLBACK_CATALOG[provider] || [])
  return PROVIDER_GROUP_ORDER.map((key) => ({
    label: providerGroupLabel(key),
    options: (key === provider ? current : (catalog[key] || [])).map((m) => ({ value: m, label: m })),
  }))
}

const CLOUD_DEFAULT_MODEL: Partial<Record<ProviderKey, string>> = {
  dashscope: 'qwen-plus', openai: 'gpt-5-mini', gemini: 'gemini-3.8-flash', deepseek: 'deepseek-flash',
  seed: 'doubao-seed-2-1-lite-260915', kimi: 'kimi-k2.6', glm: 'glm-5.3', grok: 'grok-4.6',
}

type SectionKey = 'model' | 'speech' | 'app' | 'publish' | 'cover' | 'feedback'
const NAV: Array<{ key: SectionKey; label: string }> = [
  { key: 'model', get label() { return t("模型") } },
  { key: 'speech', get label() { return t("转写") } },
  { key: 'app', get label() { return t("应用") } },
  { key: 'publish', get label() { return t("发布") } },
  { key: 'cover', get label() { return t("封面") } },
  { key: 'feedback', get label() { return t("反馈") } },
]

// Calm Premium settings — left nav + setting rows (see DESIGN.md → App Layer)
const SettingsPage: React.FC = () => {
  useTranslation()
  const [form] = Form.useForm()
  const location = useLocation()
  const initialSection = useMemo<SectionKey>(() => {
    const s = new URLSearchParams(location.search).get('section')
    return (NAV.find((n) => n.key === s)?.key as SectionKey) || 'model'
  }, [location.search])
  const [active, setActive] = useState<SectionKey>(initialSection)
  const [loading, setLoading] = useState(false)
  const [testing, setTesting] = useState(false)
  const [currentProvider, setCurrentProvider] = useState<any>({})
  const [selectedProvider, setSelectedProvider] = useState<ProviderKey>('dashscope')
  // 本地预设的模型探测：{ reachable, models } —— 让用户从下拉里选，而不是手敲 qwen2.5:7b
  const [localModels, setLocalModels] = useState<{ loading: boolean; reachable: boolean | null; models: string[] }>({ loading: false, reachable: null, models: [] })
  const [cloudModels, setCloudModels] = useState<{
    loading: boolean
    source: 'catalog' | 'live'
    reachable: boolean
    models: string[]
    catalog: Record<string, string[]>
  }>({ loading: false, source: 'catalog', reachable: false, models: FALLBACK_CATALOG.dashscope, catalog: FALLBACK_CATALOG })
  const [dashscopeRegion, setDashscopeRegion] = useState<DashscopeRegion>('cn')
  const [analyticsOn, setAnalyticsOn] = useState(isAnalyticsEnabled())
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const runtime = getRuntimeInfo()

  useEffect(() => { loadData() }, [])
  useEffect(() => { setActive(initialSection) }, [initialSection])

  // 桌面 / Docker / 本地脚本三种形态都走同一组 /settings 接口：settings.json 落在后端数据目录，
  // API 进程与 worker 按 mtime 热重载。Docker 用户以前只能改 .env（#100）。
  const loadData = async () => {
    try {
      const [settings, provider] = await Promise.allSettled([
        settingsApi.getSettings(),
        settingsApi.getCurrentProvider()
      ])
      if (settings.status === 'rejected') console.warn('读取设置失败:', settings.reason)
      const settingsData = settings.status === 'fulfilled' ? settings.value : {}
      const providerData = provider.status === 'fulfilled'
        ? provider.value
        : { available: false, provider: 'dashscope', display_name: t("阿里通义千问"), model: 'qwen-plus' }
      // 以 settings.json 里保存的提供商为准；旧配置没有该字段时退回后端上报的当前提供商
      const rawProvider = (settingsData.api?.api_provider || providerData.provider || 'dashscope') as string
      // 旧版把 DeepSeek 走硅基流动；现在改官方渠道，打开设置页时切过去
      const providerName = (rawProvider === 'siliconflow' ? 'deepseek' : rawProvider) as ProviderKey
      setCurrentProvider(providerData)
      const savedBaseUrl = settingsData.api?.api_base_url || ''
      const localPreset = PROVIDERS[providerName]?.local
      setDashscopeRegion(providerName === 'dashscope' && normalizeBaseUrl(savedBaseUrl) === DASHSCOPE_INTL_BASE_URL ? 'intl' : 'cn')
      form.setFieldsValue({
        llm_provider: providerName,
        dashscope_api_key: settingsData.api?.api_keys?.dashscope || '',
        openai_api_key: settingsData.api?.api_keys?.openai || '',
        openai_base_url: localPreset || providerName === 'dashscope' ? '' : savedBaseUrl,
        // 本地预设只在改过默认地址时才把地址填进表单
        local_base_url: localPreset && savedBaseUrl && savedBaseUrl !== localPreset.baseUrl ? savedBaseUrl : '',
        gemini_api_key: settingsData.api?.api_keys?.gemini || '',
        siliconflow_api_key: settingsData.api?.api_keys?.siliconflow || '',
        deepseek_api_key: settingsData.api?.api_keys?.deepseek || '',
        kimi_api_key: settingsData.api?.api_keys?.kimi || '',
        glm_api_key: settingsData.api?.api_keys?.glm || '',
        grok_api_key: settingsData.api?.api_keys?.grok || '',
        seed_api_key: settingsData.api?.api_keys?.seed || '',
        jimeng_access_key: settingsData.api?.api_keys?.jimeng_access || '',
        jimeng_secret_key: settingsData.api?.api_keys?.jimeng_secret || '',
        model_name: settingsData.api?.api_model || 'qwen-plus',
        chunk_size: settingsData.processing?.processing_chunk_size || 5000,
        min_score_threshold: settingsData.processing?.processing_min_score || 0.7,
        max_clips_per_collection: settingsData.processing?.processing_max_clips || 5
      })
      const resolved = PROVIDERS[providerName] ? providerName : 'dashscope'
      setSelectedProvider(resolved)
      if (!isLocalProvider(resolved)) void loadCloudModels(resolved)
    } catch (err) {
      console.error('加载数据失败:', err)
    }
  }

  const handleSave = async (values: any) => {
    try {
      setLoading(true)
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
            deepseek: values.deepseek_api_key || keys.deepseek || '',
            kimi: values.kimi_api_key || keys.kimi || '',
            glm: values.glm_api_key || keys.glm || '',
            grok: values.grok_api_key || keys.grok || '',
            seed: values.seed_api_key || keys.seed || '',
            jimeng_access: values.jimeng_access_key || keys.jimeng_access || '',
            jimeng_secret: values.jimeng_secret_key || keys.jimeng_secret || ''
          },
          api_provider: provider,
          api_base_url: provider === 'openai'
            ? normalizeBaseUrl(values.openai_base_url)
            : isLocalProvider(provider) ? normalizeBaseUrl(values.local_base_url)
            : isCloudPreset(provider) ? (PROVIDERS[provider].cloud?.baseUrl || '')
            : provider === 'dashscope' && dashscopeRegion === 'intl' ? DASHSCOPE_INTL_BASE_URL : '',
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
      message.success(t("已保存"))
      trackApiKeyConfigured({ provider, hasKey: isLocalProvider(provider) || !!values[PROVIDERS[provider].apiKeyField] })
      await loadData()
    } catch (err: any) {
      message.error(t("保存失败: ") + (err.message || t("未知错误")))
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
      : local ? (normalizeBaseUrl(form.getFieldValue('local_base_url')) || cfg.local!.baseUrl)
      : cfg.cloud ? cfg.cloud.baseUrl
      : selectedProvider === 'dashscope' && dashscopeRegion === 'intl' ? DASHSCOPE_INTL_BASE_URL : ''
    const modelName = normalizeModelName(form.getFieldValue('model_name'))
    if (local && !modelName) {
      message.error(t("请先选择一个模型"))
      return
    }
    // 自建兼容服务（Ollama / vLLM 等）通常不需要 key，有地址就能测
    if (!apiKey.trim() && !baseUrl) {
      message.error(t("请先填写 API Key"))
      return
    }
    try {
      setTesting(true)
      const r = await settingsApi.testApiKey(selectedProvider, apiKey, { baseUrl: baseUrl || undefined, model: modelName || undefined })
      if (r.success) message.success(t("连接正常"))
      else message.error(t("连接失败: ") + (r.error || t("未知错误")))
    } catch (err: any) {
      message.error(t("测试失败: ") + (err.message || t("未知错误")))
    } finally {
      setTesting(false)
    }
  }

  const cloudBaseUrl = (p: ProviderKey = selectedProvider) => {
    if (p === 'openai') return normalizeBaseUrl(form.getFieldValue('openai_base_url'))
    if (PROVIDERS[p]?.cloud) return PROVIDERS[p].cloud!.baseUrl
    if (p === 'dashscope' && dashscopeRegion === 'intl') return DASHSCOPE_INTL_BASE_URL
    return ''
  }

  const loadCloudModels = async (p?: ProviderKey, opts: { refresh?: boolean } = {}) => {
    const provider = p || selectedProvider
    if (isLocalProvider(provider)) return
    setCloudModels((s) => ({ ...s, loading: true }))
    try {
      const r = await settingsApi.getAvailableModels({
        provider,
        apiKey: form.getFieldValue(PROVIDERS[provider].apiKeyField) || '',
        baseUrl: cloudBaseUrl(provider) || undefined,
        refresh: opts.refresh,
      })
      setCloudModels({
        loading: false,
        source: r.source === 'live' ? 'live' : 'catalog',
        reachable: !!r.reachable,
        models: r.models?.length ? r.models : (r.catalog?.[provider] || FALLBACK_CATALOG[provider] || []),
        catalog: r.catalog && Object.keys(r.catalog).length ? r.catalog : FALLBACK_CATALOG,
      })
    } catch {
      setCloudModels((s) => ({ ...s, loading: false, source: 'catalog', reachable: false }))
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
    if (preset) {
      // 从云端切到本地时，qwen-plus 这类云端模型名对本地服务没意义
      const known = knownCloudModels(cloudModels.catalog, cloudModels.models)
      if (!current || known.has(current)) {
        form.setFieldsValue({ model_name: preset.defaultModel || undefined })
      }
      void detectLocalModels(p, form.getFieldValue('local_base_url'))
    } else {
      // 换提供商时，别把 qwen-plus / gpt-5 这类别人的名字带过去
      const known = knownCloudModels(cloudModels.catalog, cloudModels.models)
      const own = new Set((cloudModels.catalog[p] || FALLBACK_CATALOG[p] || []))
      if (isLocalProvider(prev) || !current || (known.has(current) && !own.has(current))) {
        form.setFieldsValue({ model_name: CLOUD_DEFAULT_MODEL[p] })
      }
      void loadCloudModels(p)
    }
  }

  // 打开设置页 / 切换通义站点时，顺手拉一次模型名单
  useEffect(() => {
    if (isLocalProvider(selectedProvider)) void detectLocalModels(selectedProvider, form.getFieldValue('local_base_url'))
    else void loadCloudModels(selectedProvider)
  }, [selectedProvider, dashscopeRegion])

  const openaiBaseUrl = Form.useWatch('openai_base_url', form)
  const usingCustomEndpoint = selectedProvider === 'openai' && !!normalizeBaseUrl(openaiBaseUrl)
  const cfg = PROVIDERS[selectedProvider]
  const localCfg = cfg.local
  const keyUrl = selectedProvider === 'dashscope' && dashscopeRegion === 'intl'
    ? 'https://bailian.console.alibabacloud.com/?tab=model#/api-key'
    : cfg.keyUrl

  return (
    <div className="ac-page">
      <header>
        <h1 className="ac-title" style={{ marginTop: 0 }}>{t("设置")}</h1>
        <div className="ac-meta">
          <span className="ac-mono">{runtime.version !== 'unknown' ? `v${runtime.version}` : 'dev'}</span>
          <span className="dot" />
          <span className="ac-mono">{runtime.os}/{runtime.arch}</span>
          {currentProvider?.available && (
            <>
              <span className="dot" />
              <span>{t("当前模型")}: <span className="ac-mono">{currentProvider.provider} · {currentProvider.model}</span></span>
            </>
          )}
        </div>
      </header>

      <div className="ac-settings" style={{ marginTop: 36 }}>
        <nav className="ac-settings-nav" aria-label={t("设置分类")}>
          {NAV.map((n) => (
            <button key={n.key} aria-current={active === n.key} onClick={() => setActive(n.key)}>{n.label}</button>
          ))}
        </nav>

        <div className="ac-settings-body">
          {/* ---------------- 模型 ---------------- */}
          {active === 'model' && (
            <Section title={t("模型")} description={t("切片分析用哪个大模型。密钥只保存在运行 AutoClip 的这台机器上，不会上传。")}>
              <Form
                form={form}
                layout="vertical"
                onFinish={handleSave}
                requiredMark={false}
                initialValues={{ llm_provider: 'dashscope', model_name: 'qwen-plus', chunk_size: 5000, min_score_threshold: 0.7, max_clips_per_collection: 5 }}
              >
                <Form.Item name="llm_provider" hidden><Input /></Form.Item>
                <div className="ac-rows">
                  <Row label={t("提供商")} hint={cfg.hint} stack>
                    <Segmented
                      size="sm"
                      ariaLabel={t("提供商")}
                      value={selectedProvider}
                      onChange={handleProviderChange}
                      options={(Object.keys(PROVIDERS) as ProviderKey[]).map((k) => ({ value: k, label: PROVIDERS[k].short }))}
                    />
                  </Row>

                  {localCfg && (
                    <Row
                      wide
                      label={t("服务地址")}
                      hint={<>{t('本地服务提示', { url: localCfg.baseUrl })} <a href={localCfg.docsUrl} onClick={(e) => { e.preventDefault(); openExternalLink(localCfg.docsUrl) }} style={{ color: 'var(--ac-accent)' }}>{localCfg.app} · {t('官网')}</a></>}
                    >
                      <Form.Item
                        name="local_base_url"
                        style={{ width: '100%' }}
                        rules={[{
                          validator: (_, value) => {
                            const url = normalizeBaseUrl(value)
                            if (!url || /^https?:\/\/\S+$/.test(url)) return Promise.resolve()
                            return Promise.reject(new Error(t("请输入以 http:// 或 https:// 开头的地址")))
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

                  {selectedProvider === 'dashscope' && (
                    <Row
                      label={t("站点")}
                      hint={dashscopeRegion === 'intl'
                        ? <>{t("国际站（alibabacloud.com）的 Key，请求发往")} <span className="ac-mono">dashscope-intl.aliyuncs.com</span>。</>
                        : t("在阿里云中国站（aliyun.com）开通的 Key 选这个；海外账号选国际站。")}
                    >
                      <Segmented
                        size="sm"
                        ariaLabel={t("通义千问站点")}
                        value={dashscopeRegion}
                        onChange={setDashscopeRegion}
                        options={[{ value: 'cn', label: t("中国站") }, { value: 'intl', label: t("国际站") }]}
                      />
                    </Row>
                  )}

                  {selectedProvider === 'openai' && (
                    <Row
                      wide
                      label={t("接口地址")}
                      hint={<>{t("留空用 OpenAI 官方地址。兼容服务填自己的，例如")} <span className="ac-mono">https://api.deepseek.com/v1</span>、<span className="ac-mono">http://localhost:11434/v1</span>（Ollama）。</>}
                    >
                      <Form.Item
                        name="openai_base_url"
                        style={{ width: '100%' }}
                        rules={[{
                          validator: (_, value) => {
                            const url = normalizeBaseUrl(value)
                            if (!url || /^https?:\/\/\S+$/.test(url)) return Promise.resolve()
                            return Promise.reject(new Error(t("请输入以 http:// 或 https:// 开头的地址")))
                          },
                        }]}
                      >
                        <Input placeholder="https://api.openai.com/v1" allowClear className="ac-mono" onBlur={() => void loadCloudModels()} />
                      </Form.Item>
                    </Row>
                  )}

                  {!localCfg && <Row
                    wide
                    label="API Key"
                    hint={usingCustomEndpoint
                      ? t("自建 / 本地兼容服务不校验密钥时可留空。")
                      : <><a href={keyUrl} onClick={(e) => { e.preventDefault(); openExternalLink(keyUrl) }} style={{ color: 'var(--ac-accent)' }}>{cfg.name}{selectedProvider === 'dashscope' && dashscopeRegion === 'intl' ? ' · ' + t("国际站") : ''} · {t("控制台")}</a></>}
                  >
                    <Form.Item
                      name={cfg.apiKeyField}
                      style={{ width: '100%' }}
                      rules={usingCustomEndpoint ? [] : [
                        { required: true, message: t("请输入 API Key") },
                        { min: 10, message: t("API Key 长度不能少于 10 位") }
                      ]}
                    >
                      <Input.Password placeholder={cfg.placeholder} className="ac-mono" onBlur={() => void loadCloudModels()} />
                    </Form.Item>
                  </Row>}

                  <Row
                    wide
                    label={t("模型")}
                    hint={localCfg
                      ? (localModels.loading
                          ? t("正在检测本地服务…")
                          : localModels.reachable
                            ? <>{t("已连接模型数量", { count: localModels.models.length })} <a onClick={() => void detectLocalModels(selectedProvider, form.getFieldValue('local_base_url'))} style={{ color: 'var(--ac-accent)', cursor: 'pointer' }}>{t("刷新")}</a></>
                            : localModels.reachable === false
                              ? <>{t('服务未连接', { app: localCfg.app })} <a onClick={() => void detectLocalModels(selectedProvider, form.getFieldValue('local_base_url'))} style={{ color: 'var(--ac-accent)', cursor: 'pointer' }}>{t('重新检测')}</a>{localCfg.defaultModel && <div className="ac-mono">ollama pull {localCfg.defaultModel}</div>}</>
                              : t("从本地服务已加载的模型中选择。"))
                      : cloudModels.loading
                        ? t("正在拉取最新模型列表…")
                        : cloudModels.source === 'live'
                          ? <>{t("已拉取最新模型数量", { count: cloudModels.models.length })} <a onClick={() => void loadCloudModels(selectedProvider, { refresh: true })} style={{ color: 'var(--ac-accent)', cursor: 'pointer' }}>{t("刷新")}</a></>
                          : usingCustomEndpoint
                            ? <>{t("填该服务实际提供的模型名（如 glm-4-flash、deepseek-chat、qwen2.5:7b），回车确认。")} <a onClick={() => void loadCloudModels(selectedProvider, { refresh: true })} style={{ color: 'var(--ac-accent)', cursor: 'pointer' }}>{t("刷新")}</a></>
                            : <>{t("可直接输入模型名，回车确认。")} {t("填写密钥后可拉取该账号可用的最新模型。")} <a onClick={() => void loadCloudModels(selectedProvider, { refresh: true })} style={{ color: 'var(--ac-accent)', cursor: 'pointer' }}>{t("刷新")}</a></>}
                  >
                    <Form.Item name="model_name" style={{ width: '100%' }} rules={[{ required: true, message: t("请输入或选择模型") }]}>
                      <Select
                        placeholder={localCfg ? (localCfg.defaultModel || t("选择或输入模型名")) : 'qwen-plus'}
                        showSearch
                        allowClear
                        mode="tags"
                        maxCount={1}
                        loading={localCfg ? localModels.loading : cloudModels.loading}
                        className="ac-mono"
                        options={(localCfg
                          ? localModels.models.map((m) => ({ value: m, label: m }))
                          : cloudModelOptions(selectedProvider, cloudModels)) as any}
                      />
                    </Form.Item>
                  </Row>

                  {selectedProvider === 'deepseek' && (
                    <Row
                      wide
                      label="DeepSeek"
                      hint={t("切片分析会关闭 DeepSeek 的思考模式，避免按长段推理输出计费。长视频仍会按大约 30 分钟一块、分几步调用；刷新页面不会重新计费，重新开始处理才会。")}
                    />
                  )}

                  <Row label={t("连接测试")} hint={localCfg ? t("保存前先测一下本地服务和模型是否可用。") : t("保存前先测一下密钥和模型是否可用。")}>
                    <Btn size="sm" loading={testing} onClick={handleTest}>{t("测试连接")}</Btn>
                  </Row>
                </div>

                <div className="ac-eyebrow" style={{ marginTop: 40, marginBottom: 12 }}>{t("切片参数")}</div>
                <div className="ac-rows">
                  <Row label={t("文本分块大小")} hint={t("每次送给模型分析的字幕长度。越大越连贯、越慢，建议 5000。")}>
                    <Form.Item name="chunk_size">
                      <input className="ac-input ac-input--mono" type="number" min={1000} step={500} style={{ width: 120, textAlign: 'right' }} />
                    </Form.Item>
                    <span className="ac-unit">{t("字符")}</span>
                  </Row>
                  <Row label={t("最低评分阈值")} hint={t("低于此分的片段会被丢掉。切片为 0 时可以调低。")}>
                    <Form.Item name="min_score_threshold">
                      <input className="ac-input ac-input--mono" type="number" min={0} max={1} step={0.05} style={{ width: 120, textAlign: 'right' }} />
                    </Form.Item>
                    <span className="ac-unit" />
                  </Row>
                  <Row label={t("每个合集最多切片")} hint={t("AI 推荐合集时，一个主题最多串几条。")}>
                    <Form.Item name="max_clips_per_collection">
                      <input className="ac-input ac-input--mono" type="number" min={1} max={20} style={{ width: 120, textAlign: 'right' }} />
                    </Form.Item>
                    <span className="ac-unit">{t("条")}</span>
                  </Row>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 12, marginTop: 28 }}>
                  {currentProvider?.available && (
                    <StatusDot tone="ok" label={<>{t("已配置")}: <span className="ac-mono">{PROVIDERS[currentProvider.provider as ProviderKey]?.name || currentProvider.display_name} · {currentProvider.model}</span></>} />
                  )}
                  <Btn variant="cta" loading={loading} onClick={() => form.submit()}>{t("保存")}</Btn>
                </div>
              </Form>
            </Section>
          )}

          {/* ---------------- 转写 ---------------- */}
          {active === 'speech' && (
            <Section
              title={t("转写")}
              description={t("视频没有字幕时，用本地 Whisper 生成字幕再分析。B 站等自带字幕的视频不需要，装不装、装哪个模型由你决定。")}
            >
              <SpeechRecognitionConfig />
            </Section>
          )}

          {/* ---------------- 应用 ---------------- */}
          {active === 'app' && (
            <AppSection analyticsOn={analyticsOn} onAnalyticsChange={(on) => { setAnalyticsEnabled(on); setAnalyticsOn(on) }} />
          )}

          {active === 'publish' && <PublishSettings />}

          {active === 'cover' && <CoverSettings />}

          {/* ---------------- 反馈 ---------------- */}
          {active === 'feedback' && (
            <Section title={t("反馈")} description={t("哪里不对、想要什么，直接说。运行环境会自动附上，不含视频内容与 API 密钥。正文会公开出现在 GitHub。")}>
              <div className="ac-rows">
                <Row label={t("发送反馈")} hint={t("在应用内写一句话即可。故障会进 GitHub Issue，想法会进 Discussions。")}>
                  <Btn variant="cta" size="sm" style={{ height: 32, fontSize: 13, padding: '0 16px' }} onClick={() => setFeedbackOpen(true)}>
                    <Icon.Chat size={13} />{t("写反馈")}</Btn>
                </Row>
                <Row label={t("出了问题")} hint={t("版本、平台和模型写在 Issue 里，方便复现。")}>
                  <Btn size="sm" onClick={() => openExternalLink(FEEDBACK_ISSUES_URL)}>{t("报告问题")}<Icon.External size={12} /></Btn>
                </Row>
                <Row label={t("想法与用法")} hint={t("希望支持的能力和你的用法发到 Discussions，不要为此开 Issue。")}>
                  <Btn size="sm" onClick={() => openExternalLink(FEEDBACK_DISCUSSIONS_URL)}>{t("去讨论")}<Icon.External size={12} /></Btn>
                </Row>
                <Row label={t("当前状态与已知问题")} hint={t("发版节奏、已知 bug 与解决办法都在这条置顶 Issue 里。")}>
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
  useTranslation()
  const { theme, setTheme } = useTheme()
  const [autostart, setAutostart] = useState(false)
  const [busy, setBusy] = useState(false)
  const [desktop, setDesktop] = useState(false)
  const [crashOn, setCrashOn] = useState(isCrashReportsEnabled())
  const [version, setVersion] = useState('')
  const appUpdate = useAppUpdate()

  useEffect(() => {
    (async () => {
      try {
        const isDesktop = await isDesktopMode()
        setDesktop(isDesktop)
        setVersion(await getAppVersion())
        if (isDesktop) {
          const { invoke } = await import('@tauri-apps/api/core')
          setAutostart(Boolean(await invoke('is_autostart_enabled')))
        }
        try {
          const privacy = await settingsApi.getPrivacy()
          if (typeof privacy?.crash_reports === 'boolean') {
            setCrashReportsEnabled(privacy.crash_reports)
            setCrashOn(privacy.crash_reports)
          }
        } catch {
          /* 后端未起或非桌面数据目录时用 localStorage */
        }
      } catch (err) {
        console.error('检查自动启动状态失败:', err)
      }
    })()
  }, [])

  const toggleAutostart = async (enabled: boolean) => {
    if (!desktop) { message.error(t("此功能仅在桌面应用中可用")); return }
    setBusy(true)
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      await invoke(enabled ? 'enable_autostart' : 'disable_autostart')
      setAutostart(enabled)
    } catch (err) {
      console.error('切换自动启动状态失败:', err)
      message.error(t("操作失败: {{value1}}", { value1: err }))
    } finally {
      setBusy(false)
    }
  }

  const toggleCrashReports = async (enabled: boolean) => {
    setCrashReportsEnabled(enabled)
    setCrashOn(enabled)
    try {
      await settingsApi.updatePrivacy({ crash_reports: enabled })
    } catch {
      message.warning(t("前端开关已生效，但后端隐私设置保存失败，请重试。"))
    }
  }

  const handleCheckUpdate = async () => {
    if (!desktop && !appUpdate.preview) { message.info(t('检查更新仅在桌面应用中可用')); return }
    try {
      const result = await appUpdate.checkNow()
      if (result === 'current') {
        const current = appUpdate.currentVersion || version
        message.success(current ? t('已是最新版本（{{version}}）', { version: current }) : t('已是最新版本'))
      }
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err)
      if (text === 'desktop-only') message.info(t('检查更新仅在桌面应用中可用'))
      else message.error(t('检查更新失败: {{error}}', { error: text.split('{{').join('{') }))
    }
  }

  const shownVersion = appUpdate.currentVersion || version
  const versionHint = appUpdate.phase === 'ready' || appUpdate.phase === 'restarting'
    ? t('可更新到 {{version}}', { version: appUpdate.version })
    : appUpdate.phase === 'downloading'
      ? t('正在准备 {{version}}', { version: appUpdate.version })
      : appUpdate.phase === 'failed'
        ? t('更新没有下载完：{{error}}', { error: appUpdate.error })
        : shownVersion
          ? t('当前 {{version}}', { version: shownVersion })
          : t('桌面应用可检查 GitHub Release 上的更新。')

  return (
    <Section title={t("应用")} description={t("外观、启动与隐私。")}>
      <div className="ac-rows">
        <Row label={t("外观")} hint={t("首次启动跟随系统。")}>
          <Segmented size="sm" ariaLabel={t("外观")} value={theme} onChange={setTheme} options={[{ value: 'light', label: t("浅色") }, { value: 'dark', label: t("深色") }]} />
        </Row>
        <Row label={t("开机自动启动")} hint={t("启用后随系统启动，可从托盘打开。仅桌面应用可用。")}>
          <Switch checked={autostart} onChange={toggleAutostart} loading={busy} disabled={!desktop} />
        </Row>
        {(desktop || appUpdate.preview) && (
          <Row label={t('版本')} hint={versionHint}>
            {appUpdate.phase === 'ready' || appUpdate.phase === 'restarting' ? (
              <Btn size="sm" variant="cta" loading={appUpdate.phase === 'restarting'} onClick={() => void appUpdate.restart()}>{t('更新并重启')}</Btn>
            ) : appUpdate.phase === 'downloading' ? (
              <Btn size="sm" onClick={appUpdate.showToast}>{t('查看进度')}</Btn>
            ) : appUpdate.phase === 'failed' ? (
              <Btn size="sm" onClick={() => void appUpdate.retry()}>{t('重试')}</Btn>
            ) : (
              <Btn size="sm" loading={appUpdate.phase === 'checking'} onClick={() => void handleCheckUpdate()}>{t('检查更新')}</Btn>
            )}
          </Row>
        )}
        <Row label={t("匿名使用统计")} hint={t("只采集功能使用、出片成功 / 失败等匿名事件，不含视频内容、字幕文本或 API 密钥。关闭后仍可在反馈里主动发送。")}>
          <Switch checked={analyticsOn} onChange={onAnalyticsChange} />
        </Row>
        <Row label={t("崩溃报告")} hint={t("把崩溃栈发到 Sentry，便于修复。不含视频内容、字幕或 API 密钥。未配置上报地址时不会发送。")}>
          <Switch checked={crashOn} onChange={toggleCrashReports} />
        </Row>
      </div>
    </Section>
  )
}

export default SettingsPage
