import React, { useState, useEffect, useMemo } from 'react'
import { Form, Input, Select, Switch, message } from 'antd'
import { useLocation } from 'react-router-dom'
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

type ProviderKey = 'dashscope' | 'openai' | 'gemini' | 'siliconflow'
const PROVIDERS: Record<ProviderKey, { name: string; short: string; hint: string; apiKeyField: string; placeholder: string; keyUrl: string }> = {
  dashscope: { name: '阿里通义千问', short: '通义千问', hint: '阿里云 DashScope。国内直连，qwen-plus 性价比高。', apiKeyField: 'dashscope_api_key', placeholder: 'sk-…', keyUrl: 'https://dashscope.console.aliyun.com/apiKey' },
  openai: { name: 'OpenAI / 兼容接口', short: 'OpenAI 兼容', hint: 'OpenAI，或任何兼容接口：智谱、DeepSeek、OpenRouter、Ollama、vLLM。', apiKeyField: 'openai_api_key', placeholder: 'sk-…（本地模型可留空）', keyUrl: 'https://platform.openai.com/api-keys' },
  gemini: { name: 'Google Gemini', short: 'Gemini', hint: 'Google AI Studio 的 Gemini 系列。', apiKeyField: 'gemini_api_key', placeholder: 'AIza…', keyUrl: 'https://aistudio.google.com/apikey' },
  siliconflow: { name: '硅基流动', short: '硅基流动', hint: 'SiliconFlow 聚合平台，DeepSeek / Qwen 等开源模型。', apiKeyField: 'siliconflow_api_key', placeholder: 'sk-…', keyUrl: 'https://cloud.siliconflow.cn/account/ak' },
}

const MODEL_GROUPS: Array<{ label: string; models: string[] }> = [
  { label: '通义千问', models: ['qwen-plus', 'qwen-turbo', 'qwen-max', 'qwen-long'] },
  { label: 'OpenAI', models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4.1', 'gpt-4.1-mini'] },
  { label: 'Gemini', models: ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-1.5-pro', 'gemini-1.5-flash'] },
  { label: '硅基流动 / 开源', models: ['deepseek-ai/DeepSeek-V3', 'deepseek-chat', 'Qwen/Qwen2.5-72B-Instruct'] },
]

type SectionKey = 'model' | 'speech' | 'app' | 'feedback'
const NAV: Array<{ key: SectionKey; label: string }> = [
  { key: 'model', label: '模型' },
  { key: 'speech', label: '转写' },
  { key: 'app', label: '应用' },
  { key: 'feedback', label: '反馈' },
]

// Calm Premium settings — left nav + setting rows (see DESIGN.md → App Layer)
const SettingsPage: React.FC = () => {
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
        form.setFieldsValue({
          llm_provider: providerName,
          dashscope_api_key: settingsData.api?.api_keys?.dashscope || '',
          openai_api_key: settingsData.api?.api_keys?.openai || '',
          openai_base_url: settingsData.api?.api_base_url || '',
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
        message.info('Web 模式下配置无法保存，请在桌面应用中使用')
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
          api_base_url: provider === 'openai' ? normalizeBaseUrl(values.openai_base_url) : '',
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
      message.success('已保存')
      trackApiKeyConfigured({ provider, hasKey: !!values[PROVIDERS[provider].apiKeyField] })
      await loadData()
    } catch (err: any) {
      message.error('保存失败: ' + (err.message || '未知错误'))
    } finally {
      setLoading(false)
    }
  }

  const handleTest = async () => {
    const cfg = PROVIDERS[selectedProvider]
    const apiKey: string = form.getFieldValue(cfg.apiKeyField) || ''
    const baseUrl = selectedProvider === 'openai' ? normalizeBaseUrl(form.getFieldValue('openai_base_url')) : ''
    const modelName = normalizeModelName(form.getFieldValue('model_name'))
    // 自建兼容服务（Ollama / vLLM 等）通常不需要 key，有地址就能测
    if (!apiKey.trim() && !baseUrl) {
      message.error('请先填写 API Key')
      return
    }
    try {
      setTesting(true)
      const r = await settingsApi.testApiKey(selectedProvider, apiKey, { baseUrl: baseUrl || undefined, model: modelName || undefined })
      if (r.success) message.success('连接正常')
      else message.error('连接失败: ' + (r.error || '未知错误'))
    } catch (err: any) {
      message.error('测试失败: ' + (err.message || '未知错误'))
    } finally {
      setTesting(false)
    }
  }

  const handleProviderChange = (p: ProviderKey) => {
    setSelectedProvider(p)
    form.setFieldsValue({ llm_provider: p })
  }

  const openaiBaseUrl = Form.useWatch('openai_base_url', form)
  const usingCustomEndpoint = selectedProvider === 'openai' && !!normalizeBaseUrl(openaiBaseUrl)
  const cfg = PROVIDERS[selectedProvider]

  return (
    <div className="ac-page">
      <header>
        <h1 className="ac-title" style={{ marginTop: 0 }}>设置</h1>
        <div className="ac-meta">
          <span className="ac-mono">{runtime.version !== 'unknown' ? `v${runtime.version}` : 'dev'}</span>
          <span className="dot" />
          <span className="ac-mono">{runtime.os}/{runtime.arch}</span>
          {currentProvider?.available && (
            <>
              <span className="dot" />
              <span>当前模型 <span className="ac-mono">{currentProvider.provider} · {currentProvider.model}</span></span>
            </>
          )}
        </div>
      </header>

      <div className="ac-settings" style={{ marginTop: 36 }}>
        <nav className="ac-settings-nav" aria-label="设置分类">
          {NAV.map((n) => (
            <button key={n.key} aria-current={active === n.key} onClick={() => setActive(n.key)}>{n.label}</button>
          ))}
        </nav>

        <div className="ac-settings-body">
          {/* ---------------- 模型 ---------------- */}
          {active === 'model' && (
            <Section title="模型" description="切片分析用哪个大模型。密钥只保存在本机，不会上传。">
              <Form
                form={form}
                layout="vertical"
                onFinish={handleSave}
                requiredMark={false}
                initialValues={{ llm_provider: 'dashscope', model_name: 'qwen-plus', chunk_size: 5000, min_score_threshold: 0.7, max_clips_per_collection: 5 }}
              >
                <Form.Item name="llm_provider" hidden><Input /></Form.Item>
                <div className="ac-rows">
                  <Row label="提供商" hint={cfg.hint} top>
                    <Segmented
                      size="sm"
                      ariaLabel="提供商"
                      value={selectedProvider}
                      onChange={handleProviderChange}
                      options={(Object.keys(PROVIDERS) as ProviderKey[]).map((k) => ({ value: k, label: PROVIDERS[k].short }))}
                    />
                  </Row>

                  {selectedProvider === 'openai' && (
                    <Row
                      wide
                      label="接口地址"
                      hint={<>留空用 OpenAI 官方地址。兼容服务填自己的，例如 <span className="ac-mono">https://api.deepseek.com/v1</span>、<span className="ac-mono">http://localhost:11434/v1</span>（Ollama）。</>}
                    >
                      <Form.Item
                        name="openai_base_url"
                        style={{ width: '100%' }}
                        rules={[{
                          validator: (_, value) => {
                            const url = normalizeBaseUrl(value)
                            if (!url || /^https?:\/\/\S+$/.test(url)) return Promise.resolve()
                            return Promise.reject(new Error('请输入以 http:// 或 https:// 开头的地址'))
                          },
                        }]}
                      >
                        <Input placeholder="https://api.openai.com/v1" allowClear className="ac-mono" />
                      </Form.Item>
                    </Row>
                  )}

                  <Row
                    wide
                    label="API Key"
                    hint={usingCustomEndpoint
                      ? '自建 / 本地兼容服务不校验密钥时可留空。'
                      : <>在 <a href={cfg.keyUrl} onClick={(e) => { e.preventDefault(); openExternalLink(cfg.keyUrl) }} style={{ color: 'var(--ac-accent)' }}>{cfg.name} 控制台</a> 获取。</>}
                  >
                    <Form.Item
                      name={cfg.apiKeyField}
                      style={{ width: '100%' }}
                      rules={usingCustomEndpoint ? [] : [
                        { required: true, message: '请输入 API Key' },
                        { min: 10, message: 'API Key 长度不能少于 10 位' }
                      ]}
                    >
                      <Input.Password placeholder={cfg.placeholder} className="ac-mono" />
                    </Form.Item>
                  </Row>

                  <Row
                    wide
                    label="模型"
                    hint={usingCustomEndpoint
                      ? '填该服务实际提供的模型名（如 glm-4-flash、deepseek-chat、qwen2.5:7b），回车确认。'
                      : '可直接输入模型名，回车确认。'}
                  >
                    <Form.Item name="model_name" style={{ width: '100%' }} rules={[{ required: true, message: '请输入或选择模型' }]}>
                      <Select
                        placeholder="qwen-plus"
                        showSearch
                        allowClear
                        mode="tags"
                        maxCount={1}
                        className="ac-mono"
                        options={MODEL_GROUPS.map((g) => ({ label: g.label, options: g.models.map((m) => ({ value: m, label: m })) }))}
                      />
                    </Form.Item>
                  </Row>

                  <Row label="连接测试" hint="保存前先测一下密钥和模型是否可用。">
                    <Btn size="sm" loading={testing} onClick={handleTest}>测试连接</Btn>
                  </Row>
                </div>

                <div className="ac-eyebrow" style={{ marginTop: 40, marginBottom: 12 }}>切片参数</div>
                <div className="ac-rows">
                  <Row label="文本分块大小" hint="每次送给模型分析的字幕长度。越大越连贯、越慢，建议 5000。">
                    <Form.Item name="chunk_size">
                      <input className="ac-input ac-input--mono" type="number" min={1000} step={500} style={{ width: 120, textAlign: 'right' }} />
                    </Form.Item>
                    <span className="ac-unit">字符</span>
                  </Row>
                  <Row label="最低评分阈值" hint="低于此分的片段会被丢掉。切片为 0 时可以调低。">
                    <Form.Item name="min_score_threshold">
                      <input className="ac-input ac-input--mono" type="number" min={0} max={1} step={0.05} style={{ width: 120, textAlign: 'right' }} />
                    </Form.Item>
                    <span className="ac-unit" />
                  </Row>
                  <Row label="每个合集最多切片" hint="AI 推荐合集时，一个主题最多串几条。">
                    <Form.Item name="max_clips_per_collection">
                      <input className="ac-input ac-input--mono" type="number" min={1} max={20} style={{ width: 120, textAlign: 'right' }} />
                    </Form.Item>
                    <span className="ac-unit">条</span>
                  </Row>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 12, marginTop: 28 }}>
                  {currentProvider?.available && (
                    <StatusDot tone="ok" label={<>已配置 <span className="ac-mono">{currentProvider.display_name} · {currentProvider.model}</span></>} />
                  )}
                  <Btn variant="cta" loading={loading} onClick={() => form.submit()}>保存</Btn>
                </div>
              </Form>
            </Section>
          )}

          {/* ---------------- 转写 ---------------- */}
          {active === 'speech' && (
            <Section
              title="转写"
              description="视频没有字幕时，用本地 Whisper 生成字幕再分析。B 站等自带字幕的视频不需要，装不装、装哪个模型由你决定。"
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
            <Section title="反馈" description="哪里不对、想要什么，直接说。运行环境会自动附上，不含视频内容与 API 密钥。">
              <div className="ac-rows">
                <Row label="发送反馈" hint="在应用内写一句话即可，我们每周统一看。">
                  <Btn variant="cta" size="sm" style={{ height: 32, fontSize: 13, padding: '0 16px' }} onClick={() => setFeedbackOpen(true)}>
                    <Icon.Chat size={13} /> 写反馈
                  </Btn>
                </Row>
                <Row label="反馈表单" hint="不想在应用里写、或想附截图 / 日志时用。">
                  <Btn size="sm" onClick={() => openExternalLink(FEEDBACK_FORM_URL)}>打开表单 <Icon.External size={12} /></Btn>
                </Row>
                <Row label="GitHub" hint="开发者可直接提 Issue（有模板），或去 Discussions 讨论。">
                  <Btn size="sm" onClick={() => openExternalLink(FEEDBACK_ISSUES_URL)}>新建 Issue <Icon.External size={12} /></Btn>
                </Row>
                <Row label="当前状态与已知问题" hint="发版节奏、已知 bug 与解决办法都在这条置顶 Issue 里。">
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
    if (!desktop) { message.error('此功能仅在桌面应用中可用'); return }
    setBusy(true)
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      await invoke(enabled ? 'enable_autostart' : 'disable_autostart')
      setAutostart(enabled)
    } catch (err) {
      console.error('切换自动启动状态失败:', err)
      message.error(`操作失败: ${err}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Section title="应用" description="外观、启动与隐私。">
      <div className="ac-rows">
        <Row label="外观" hint="首次启动跟随系统。">
          <Segmented size="sm" ariaLabel="外观" value={theme} onChange={setTheme} options={[{ value: 'light', label: '浅色' }, { value: 'dark', label: '深色' }]} />
        </Row>
        <Row label="开机自动启动" hint="启用后随系统启动，可从托盘打开。仅桌面应用可用。">
          <Switch checked={autostart} onChange={toggleAutostart} loading={busy} disabled={!desktop} />
        </Row>
        <Row label="匿名使用统计" hint="只采集功能使用、出片成功 / 失败等匿名事件，不含视频内容、字幕文本或 API 密钥。关闭后应用内反馈将改用表单。">
          <Switch checked={analyticsOn} onChange={onAnalyticsChange} />
        </Row>
        <Row label="B 站账号" hint="多账号管理与一键投稿，开发中。">
          <span className="ac-hint" style={{ margin: 0 }}>即将推出</span>
        </Row>
      </div>
    </Section>
  )
}

export default SettingsPage
