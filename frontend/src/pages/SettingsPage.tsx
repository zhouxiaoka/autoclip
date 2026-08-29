import React, { useState, useEffect } from 'react'
import { Layout, Card, Form, Input, Button, Typography, Space, Alert, Divider, Row, Col, Tabs, message, Select, Tag, Switch } from 'antd'
import { KeyOutlined, SaveOutlined, ApiOutlined, SettingOutlined, InfoCircleOutlined, UserOutlined, RobotOutlined, SoundOutlined, PoweroffOutlined } from '@ant-design/icons'
import { settingsApi } from '../services/api'
import BilibiliManager from '../components/BilibiliManager'
import SpeechRecognitionConfig from '../components/SpeechRecognitionConfig'
import { isDesktopMode } from '../utils/desktopMode'
import { trackApiKeyConfigured } from '../analytics/events'
import { isAnalyticsEnabled, setAnalyticsEnabled } from '../analytics/posthog'
import './SettingsPage.css'

const { Content } = Layout
const { Title, Text, Paragraph } = Typography
const { TabPane } = Tabs

const SettingsPage: React.FC = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [showBilibiliManager, setShowBilibiliManager] = useState(false)
  const [currentProvider, setCurrentProvider] = useState<any>({})
  const [selectedProvider, setSelectedProvider] = useState('dashscope')
  const [analyticsOn, setAnalyticsOn] = useState(isAnalyticsEnabled())

  // 提供商配置
  const providerConfig = {
    dashscope: {
      name: 'Alibaba Qwen',
      icon: <RobotOutlined />,
      color: '#1890ff',
      description: 'Alibaba DashScope / Qwen models',
      apiKeyField: 'dashscope_api_key',
      placeholder: 'Enter your DashScope API key'
    },
    openai: {
      name: 'OpenAI',
      icon: <RobotOutlined />,
      color: '#52c41a',
      description: 'OpenAI GPT models',
      apiKeyField: 'openai_api_key',
      placeholder: 'Enter your OpenAI API key'
    },
    gemini: {
      name: 'Google Gemini',
      icon: <RobotOutlined />,
      color: '#faad14',
      description: 'Google Gemini models',
      apiKeyField: 'gemini_api_key',
      placeholder: 'Enter your Gemini API key'
    },
    siliconflow: {
      name: 'SiliconFlow',
      icon: <RobotOutlined />,
      color: '#722ed1',
      description: 'SiliconFlow model API',
      apiKeyField: 'siliconflow_api_key',
      placeholder: 'Enter your SiliconFlow API key'
    }
  }

  // 加载数据
  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
        const [settings, models, provider] = await Promise.allSettled([
          settingsApi.getSettings(),
          settingsApi.getAvailableModels(),
          settingsApi.getCurrentProvider()
        ])
        
        const failedRequests = [settings, models, provider].filter(result => result.status === 'rejected')
        if (failedRequests.length > 0) {
          console.warn('Some settings API requests failed:', failedRequests.map(r => (r as PromiseRejectedResult).reason))
        }
        
        const settingsData = settings.status === 'fulfilled' ? settings.value : {}
        const providerData = provider.status === 'fulfilled'
          ? provider.value
          : { available: false, provider: 'gemini', display_name: 'Google Gemini', model: 'gemini-3.6-flash' }
        const providerName = settingsData.api?.api_provider || providerData.provider || 'gemini'
        setCurrentProvider({ ...providerData, provider: providerName })
        
        const geminiAliases: Record<string, string> = {
          'gemini-pro': 'gemini-3.6-flash',
          'gemini-1.5-flash': 'gemini-3.6-flash',
          'gemini-1.5-pro': 'gemini-3.1-pro-preview',
          'gemini-2.0-flash': 'gemini-3.6-flash',
          'gemini-2.5-flash': 'gemini-3.6-flash',
          'gemini-2.5-pro': 'gemini-3.1-pro-preview',
        }
        const savedModel = settingsData.api?.api_model
        let modelName = Array.isArray(savedModel) ? savedModel[0] : (savedModel || (providerName === 'gemini' ? 'gemini-3.6-flash' : 'qwen-plus'))
        if (providerName === 'gemini' && geminiAliases[modelName]) {
          modelName = geminiAliases[modelName]
        }

        const flatSettings = {
          llm_provider: providerName,
          dashscope_api_key: settingsData.api?.api_keys?.dashscope || '',
          openai_api_key: settingsData.api?.api_keys?.openai || '',
          gemini_api_key: settingsData.api?.api_keys?.gemini || '',
          siliconflow_api_key: settingsData.api?.api_keys?.siliconflow || '',
          jimeng_access_key: settingsData.api?.api_keys?.jimeng_access || '',
          jimeng_secret_key: settingsData.api?.api_keys?.jimeng_secret || '',
          model_name: modelName,
          chunk_size: settingsData.processing?.processing_chunk_size || 5000,
          min_score_threshold: settingsData.processing?.processing_min_score || 0.7,
          max_clips_per_collection: settingsData.processing?.processing_max_clips || 5
        }
        
        setSelectedProvider(providerName)
        form.setFieldsValue(flatSettings)
    } catch (error) {
      console.error('Failed to load settings:', error)
    }
  }

  // 保存配置
  const handleSave = async (values: any) => {
    try {
      setLoading(true)
      
      // 先获取现有配置，避免清空已有的API key
      let existingSettings = null
      try {
        existingSettings = await settingsApi.getSettings()
      } catch (error) {
        console.warn('获取现有配置失败，将使用默认配置:', error)
      }
      
      // 获取现有的API keys，只更新有值的字段
      const existingApiKeys = existingSettings?.api?.api_keys || {}
      
      // 转换扁平数据为后端期望的嵌套结构
      const backendSettings = {
        basic: {
          app_name: "AutoClip Desktop",
          app_version: "1.0.0",
          debug_mode: false,
          auto_start: true
        },
        service: {
          host: "127.0.0.1",
          port: 8000,
          max_memory_usage: 2048
        },
          api: {
          api_keys: {
            dashscope: values.dashscope_api_key || existingApiKeys.dashscope || "",
            openai: values.openai_api_key || existingApiKeys.openai || "",
            gemini: values.gemini_api_key || existingApiKeys.gemini || "",
            siliconflow: values.siliconflow_api_key || existingApiKeys.siliconflow || "",
            jimeng_access: values.jimeng_access_key || existingApiKeys.jimeng_access || "",
            jimeng_secret: values.jimeng_secret_key || existingApiKeys.jimeng_secret || ""
          },
          api_provider: selectedProvider,
          api_model: Array.isArray(values.model_name) ? (values.model_name[0] || "gemini-3.6-flash") : (values.model_name || "gemini-3.6-flash"),
          api_max_tokens: 4096,
          api_timeout: 30
        },
        processing: {
          processing_chunk_size: values.chunk_size || 5000,
          processing_min_score: values.min_score_threshold || 0.7,
          processing_max_clips: values.max_clips_per_collection || 5,
          processing_max_retries: 3
        },
        logs: {
          log_level: "INFO",
          log_retention_days: 7
        }
      }
      
      await settingsApi.updateSettings(backendSettings)
      message.success('Settings saved')

      // 埋点：记录配置了哪个 provider 的 key（不传 key 明文）
      const apiKeyField = providerConfig[selectedProvider as keyof typeof providerConfig]?.apiKeyField
      if (apiKeyField) {
        trackApiKeyConfigured({
          provider: selectedProvider,
          hasKey: !!values[apiKeyField],
        })
      }

      await loadData() // 重新加载数据
    } catch (error: any) {
      const detail = error?.response?.data?.detail || error?.userMessage || error?.message || 'Unknown error'
      message.error('Save failed: ' + (typeof detail === 'string' ? detail : JSON.stringify(detail)))
    } finally {
      setLoading(false)
    }
  }

  // 测试API密钥
  const handleTestApiKey = async () => {
    const apiKey = form.getFieldValue(providerConfig[selectedProvider as keyof typeof providerConfig].apiKeyField)
    
    if (!apiKey || apiKey.trim() === '') {
      message.error('Please enter an API key first')
      return
    }

    try {
      setLoading(true)
      const modelName = form.getFieldValue('model_name')
      const result = await settingsApi.testApiKey(
        selectedProvider,
        apiKey,
        Array.isArray(modelName) ? modelName[0] : modelName
      )
      if (result.success) {
        message.success('API key works')
      } else {
        message.error('API key test failed: ' + (result.error || 'Unknown error'))
      }
    } catch (error: any) {
      const detail = error?.response?.data?.detail || error?.userMessage || error?.message || 'Unknown error'
      message.error('Test failed: ' + (typeof detail === 'string' ? detail : JSON.stringify(detail)))
    } finally {
      setLoading(false)
    }
  }

  // 提供商切换
  const handleProviderChange = (provider: string) => {
    setSelectedProvider(provider)
    const defaults: Record<string, string> = {
      dashscope: 'qwen-plus',
      openai: 'gpt-4o-mini',
      gemini: 'gemini-3.6-flash',
      siliconflow: 'deepseek-chat',
    }
    form.setFieldsValue({ llm_provider: provider, model_name: defaults[provider] || 'gemini-3.6-flash' })
  }

  return (
    <Content className="settings-page">
      <div className="settings-container">
        <Title level={2} className="settings-title">
          <SettingOutlined /> Settings
        </Title>
        
        <Tabs defaultActiveKey="api" className="settings-tabs">
          <TabPane tab="AI models" key="api">
            <Card title="AI models" className="settings-card">
              <Alert
                message="Multiple providers"
                description="Pick a provider, paste your API key, then test the connection."
                type="info"
                showIcon
                className="settings-alert"
              />
              
              <Form
                form={form}
                layout="vertical"
                className="settings-form"
                onFinish={handleSave}
                initialValues={{
                  llm_provider: 'dashscope',
                  model_name: 'qwen-plus',
                  chunk_size: 5000,
                  min_score_threshold: 0.7,
                  max_clips_per_collection: 5
                }}
              >
                {/* 当前提供商状态 */}
                {currentProvider.available && (
                  <Alert
                    message={`Using: ${currentProvider.display_name} — ${currentProvider.model}`}
                    type="success"
                    showIcon
                    style={{ marginBottom: 24 }}
                  />
                )}

                {/* 提供商选择 */}
                <Form.Item
                  label="AI provider"
                  name="llm_provider"
                  className="form-item"
                  rules={[{ required: true, message: 'Please choose a provider' }]}
                >
                  <Select
                    value={selectedProvider}
                    onChange={handleProviderChange}
                    className="settings-input"
                    placeholder="Choose a provider"
                  >
                    {Object.entries(providerConfig).map(([key, config]) => (
                      <Select.Option key={key} value={key}>
                        <Space>
                          <span style={{ color: config.color }}>{config.icon}</span>
                          <span>{config.name}</span>
                          <Tag color={config.color}>{config.description}</Tag>
                        </Space>
                      </Select.Option>
                    ))}
                  </Select>
                </Form.Item>

                {/* 动态API密钥输入 */}
                <Form.Item
                  label={`${providerConfig[selectedProvider as keyof typeof providerConfig].name} API Key`}
                  name={providerConfig[selectedProvider as keyof typeof providerConfig].apiKeyField}
                  className="form-item"
                  rules={[
                    { required: true, message: 'Please enter an API key' },
                    { min: 10, message: 'API key must be at least 10 characters' }
                  ]}
                >
                  <Input.Password
                    placeholder={providerConfig[selectedProvider as keyof typeof providerConfig].placeholder}
                    prefix={<KeyOutlined />}
                    className="settings-input"
                  />
                </Form.Item>

                {/* 模型选择 - 改进版本 */}
                <Form.Item
                  label="Model"
                  name="model_name"
                  className="form-item"
                  rules={[{ required: true, message: 'Enter or choose a model' }]}
                  extra="Type a model name or pick one from the list"
                >
                  <Select
                    className="settings-input"
                    placeholder="Enter or choose a model"
                    showSearch
                    allowClear
                    dropdownRender={(menu) => (
                      <div>
                        {menu}
                        <Divider style={{ margin: '8px 0' }} />
                        <div style={{ padding: '0 8px 4px' }}>
                          <Text type="secondary" style={{ fontSize: '12px' }}>
                            Common models by provider
                          </Text>
                        </div>
                      </div>
                    )}
                  >
                    {/* 通义千问模型 */}
                    <Select.OptGroup label="Qwen (DashScope)">
                      <Select.Option value="qwen-plus">qwen-plus (Qwen Plus)</Select.Option>
                      <Select.Option value="qwen-turbo">qwen-turbo (Qwen Turbo)</Select.Option>
                      <Select.Option value="qwen-max">qwen-max (Qwen Max)</Select.Option>
                      <Select.Option value="qwen-long">qwen-long (Qwen Long)</Select.Option>
                    </Select.OptGroup>
                    
                    {/* OpenAI模型 */}
                    <Select.OptGroup label="OpenAI">
                      <Select.Option value="gpt-4o">gpt-4o (GPT-4 Omni)</Select.Option>
                      <Select.Option value="gpt-4o-mini">gpt-4o-mini (GPT-4 Omni Mini)</Select.Option>
                      <Select.Option value="gpt-4-turbo">gpt-4-turbo (GPT-4 Turbo)</Select.Option>
                      <Select.Option value="gpt-4">gpt-4 (GPT-4)</Select.Option>
                      <Select.Option value="gpt-3.5-turbo">gpt-3.5-turbo (GPT-3.5 Turbo)</Select.Option>
                    </Select.OptGroup>
                    
                    {/* Google Gemini模型 */}
                    <Select.OptGroup label="Google Gemini">
                      <Select.Option value="gemini-3.6-flash">gemini-3.6-flash (recommended for long VODs)</Select.Option>
                      <Select.Option value="gemini-3.7-flash">gemini-3.7-flash (latest Flash)</Select.Option>
                      <Select.Option value="gemini-3.1-pro-preview">gemini-3.1-pro-preview (higher quality)</Select.Option>
                      <Select.Option value="gemini-3.5-flash-lite">gemini-3.5-flash-lite (cheaper / faster)</Select.Option>
                    </Select.OptGroup>
                    
                    {/* 硅基流动模型 */}
                    <Select.OptGroup label="SiliconFlow">
                      <Select.Option value="deepseek-chat">deepseek-chat (DeepSeek Chat)</Select.Option>
                      <Select.Option value="deepseek-coder">deepseek-coder (DeepSeek Coder)</Select.Option>
                      <Select.Option value="qwen-plus">qwen-plus (Qwen Plus)</Select.Option>
                      <Select.Option value="qwen-turbo">qwen-turbo (Qwen Turbo)</Select.Option>
                    </Select.OptGroup>
                    
                  </Select>
                </Form.Item>

                <Form.Item className="form-item">
                  <Space>
                    <Button
                      type="default"
                      icon={<ApiOutlined />}
                      className="test-button"
                      onClick={handleTestApiKey}
                      loading={loading}
                    >
                      Test connection
                    </Button>
                  </Space>
                </Form.Item>

                <Divider className="settings-divider" />

                <Title level={4} className="section-title">Processing</Title>
                
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      label="Chunk size"
                      name="chunk_size"
                      className="form-item"
                    >
                      <Input 
                        type="number" 
                        placeholder="5000" 
                        addonAfter="chars" 
                        className="settings-input"
                      />
                    </Form.Item>
                  </Col>
                </Row>

                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      label="Minimum score"
                      name="min_score_threshold"
                      className="form-item"
                    >
                      <Input 
                        type="number" 
                        step="0.1" 
                        min="0" 
                        max="1" 
                        placeholder="0.7" 
                        className="settings-input"
                      />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      label="Max clips per collection"
                      name="max_clips_per_collection"
                      className="form-item"
                    >
                      <Input 
                        type="number" 
                        placeholder="5" 
                        addonAfter="clips" 
                        className="settings-input"
                      />
                    </Form.Item>
                  </Col>
                </Row>

                <Form.Item className="form-item">
                  <Button
                    type="primary"
                    htmlType="submit"
                    icon={<SaveOutlined />}
                    size="large"
                    className="save-button"
                    loading={loading}
                  >
                    Save
                  </Button>
                </Form.Item>
              </Form>
            </Card>

            <Card title="How to set this up" className="settings-card">
              <Space direction="vertical" size="large" className="instructions-space">
                <div className="instruction-item">
                  <Title level={5} className="instruction-title">
                    <InfoCircleOutlined /> 1. Choose a provider
                  </Title>
                  <Paragraph className="instruction-text">
                    Supported providers:
                    <br />• <Text strong>Alibaba Qwen</Text> — get a key from the Alibaba Cloud console
                    <br />• <Text strong>OpenAI</Text> — get a key at platform.openai.com
                    <br />• <Text strong>Google Gemini</Text> — get a key at aistudio.google.com/apikey
                    <br />• <Text strong>SiliconFlow</Text> — get a key at cloud.siliconflow.cn
                  </Paragraph>
                </div>
                
                <div className="instruction-item">
                  <Title level={5} className="instruction-title">
                    <InfoCircleOutlined /> 2. Processing options
                  </Title>
                  <Paragraph className="instruction-text">
                    • <Text strong>Chunk size</Text> — larger is faster, smaller is more precise (5000 is a good default)<br />
                    • <Text strong>Score threshold</Text> — only clips above this score are kept<br />
                    • <Text strong>Clips per collection</Text> — how many clips each collection includes
                  </Paragraph>
                </div>
                
                <div className="instruction-item">
                  <Title level={5} className="instruction-title">
                    <InfoCircleOutlined /> 3. Test the connection
                  </Title>
                  <Paragraph className="instruction-text">
                    Test the API key before saving so you know the provider is working.
                  </Paragraph>
                </div>
              </Space>
            </Card>
          </TabPane>

          <TabPane 
            tab={
              <span>
                <SoundOutlined />
                Speech-to-text
              </span>
            } 
            key="speech"
          >
            <Card title="Speech-to-text" className="settings-card">
              <Alert
                message="Caption generation"
                description="Used when a video has no subtitles. Supports local Whisper and cloud APIs."
                type="info"
                showIcon
                className="settings-alert"
              />
              
              <SpeechRecognitionConfig
                onConfigChange={(config) => {
                  console.log('语音配置已更新:', config)
                  // 移除重复的成功提示，SpeechRecognitionConfig内部已经处理
                }}
              />
            </Card>
          </TabPane>

          <TabPane 
            tab={
              <span>
                <SettingOutlined />
                App
              </span>
            } 
            key="app"
          >
            <Card title="App" className="settings-card">
              <Alert
                message="App behavior"
                description="Startup and system integration options."
                type="info"
                showIcon
                className="settings-alert"
              />
              
              <AppSettings />
            </Card>

            <Card title="Privacy" className="settings-card" style={{ marginTop: 16 }}>
              <Alert
                message="Anonymous usage stats"
                description="We collect anonymous events (feature use, success/failure). Not your videos, transcripts, or API keys. You can turn this off anytime."
                type="info"
                showIcon
                className="settings-alert"
              />
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 16 }}>
                <div>
                  <Text strong>Allow anonymous analytics</Text>
                  <Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
                    When off, nothing is sent.
                  </Paragraph>
                </div>
                <Switch
                  checked={analyticsOn}
                  onChange={(checked) => {
                    setAnalyticsEnabled(checked)
                    setAnalyticsOn(checked)
                    message.success(checked ? 'Anonymous analytics on' : 'Anonymous analytics off')
                  }}
                />
              </div>
            </Card>
          </TabPane>

          <TabPane tab="Bilibili" key="bilibili">
            <Card title="Bilibili accounts" className="settings-card">
              <div style={{ textAlign: 'center', padding: '40px 20px' }}>
                <div style={{ marginBottom: '24px' }}>
                  <UserOutlined style={{ fontSize: '48px', color: '#1890ff', marginBottom: '16px' }} />
                  <Title level={3} style={{ color: 'var(--ac-ink)', margin: '0 0 8px 0' }}>
                    Bilibili accounts
                  </Title>
                  <Text type="secondary" style={{ color: '#b0b0b0', fontSize: '16px' }}>
                    Manage accounts for uploading clips
                  </Text>
                </div>
                
                <Space size="large">
                  <Button
                    type="primary"
                    size="large"
                    icon={<UserOutlined />}
                    onClick={() => message.info('Coming soon', 3)}
                    style={{
                      borderRadius: '8px',
                      background: 'linear-gradient(45deg, #1890ff, #36cfc9)',
                      border: 'none',
                      fontWeight: 500,
                      height: '48px',
                      padding: '0 32px',
                      fontSize: '16px'
                    }}
                  >
                    Manage Bilibili accounts
                  </Button>
                </Space>
                
                <div style={{ marginTop: '32px', textAlign: 'left', maxWidth: '600px', margin: '32px auto 0' }}>
                  <Title level={4} style={{ color: 'var(--ac-ink)', marginBottom: '16px' }}>
                    Features
                  </Title>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
                    <div style={{ 
                      padding: '16px', 
                      background: 'rgba(255,255,255,0.05)', 
                      borderRadius: '8px',
                      border: '1px solid #404040'
                    }}>
                      <Text strong style={{ color: '#1890ff' }}>Multiple accounts</Text>
                      <br />
                      <Text type="secondary" style={{ color: '#b0b0b0' }}>
                        Add and switch between Bilibili accounts
                      </Text>
                    </div>
                    <div style={{ 
                      padding: '16px', 
                      background: 'rgba(255,255,255,0.05)', 
                      borderRadius: '8px',
                      border: '1px solid #404040'
                    }}>
                      <Text strong style={{ color: '#52c41a' }}>Cookie login</Text>
                      <br />
                      <Text type="secondary" style={{ color: '#b0b0b0' }}>
                        Import cookies instead of password login
                      </Text>
                    </div>
                    <div style={{ 
                      padding: '16px', 
                      background: 'rgba(255,255,255,0.05)', 
                      borderRadius: '8px',
                      border: '1px solid #404040'
                    }}>
                      <Text strong style={{ color: '#faad14' }}>Quick upload</Text>
                      <br />
                      <Text type="secondary" style={{ color: '#b0b0b0' }}>
                        Upload clips from the clip detail page
                      </Text>
                    </div>
                    <div style={{ 
                      padding: '16px', 
                      background: 'rgba(255,255,255,0.05)', 
                      borderRadius: '8px',
                      border: '1px solid #404040'
                    }}>
                      <Text strong style={{ color: '#722ed1' }}>Batch upload</Text>
                      <br />
                      <Text type="secondary" style={{ color: '#b0b0b0' }}>
                        Upload multiple clips at once
                      </Text>
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          </TabPane>
        </Tabs>

        {/* B站管理弹窗 */}
        <BilibiliManager
          visible={showBilibiliManager}
          onClose={() => setShowBilibiliManager(false)}
          onUploadSuccess={() => {
            message.success('Done')
          }}
        />
      </div>
    </Content>
  )
}

// 应用设置组件
const AppSettings: React.FC = () => {
  const [autostartEnabled, setAutostartEnabled] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    checkAutostartStatus()
  }, [])

  const checkAutostartStatus = async () => {
    try {
      const isDesktop = await isDesktopMode()
      if (isDesktop) {
        const { invoke } = await import('@tauri-apps/api/core')
        const enabled = await invoke('is_autostart_enabled')
        setAutostartEnabled(Boolean(enabled))
      }
    } catch (error) {
      console.error('检查自动启动状态失败:', error)
    }
  }

  const handleAutostartToggle = async (enabled: boolean) => {
    const isDesktop = await isDesktopMode()
    if (!isDesktop) {
      message.error('This is only available in the desktop app')
      return
    }

    setLoading(true)
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      
      if (enabled) {
        await invoke('enable_autostart')
        message.success('Launch at login enabled')
      } else {
        await invoke('disable_autostart')
        message.success('Launch at login disabled')
      }
      
      setAutostartEnabled(enabled)
    } catch (error) {
      console.error('切换自动启动状态失败:', error)
      message.error(`Failed: ${error}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card 
            size="small" 
            style={{ 
              background: 'rgba(255,255,255,0.05)', 
              border: '1px solid #404040',
              marginBottom: '16px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                  <PoweroffOutlined style={{ color: '#1890ff', marginRight: '8px' }} />
                  <Text strong style={{ color: 'var(--ac-ink)' }}>Launch at login</Text>
                </div>
                <Text type="secondary" style={{ color: '#b0b0b0' }}>
                  Start AutoClip when your computer starts
                </Text>
              </div>
              <Switch
                checked={autostartEnabled}
                onChange={handleAutostartToggle}
                loading={loading}
                checkedChildren="On"
                unCheckedChildren="Off"
              />
            </div>
          </Card>
        </Col>
      </Row>
      
      <Alert
        message="Note"
        description="Launch at login is only available in the desktop app. After enabling it, AutoClip starts with your system."
        type="info"
        showIcon
        style={{ marginTop: '16px' }}
      />
    </div>
  )
}

export default SettingsPage
