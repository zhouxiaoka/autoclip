import React, { useState, useEffect } from 'react'
import { Card, Button, Typography, Space, Alert, message, Form, Input, Select } from 'antd'
import { 
  SoundOutlined, 
  ApiOutlined, 
  CheckCircleOutlined,
  LoadingOutlined,
  LinkOutlined,
  InfoCircleOutlined
} from '@ant-design/icons'
import { ExternalLink } from '../utils/externalLinks'
import { settingsApi } from '../services/api'
import { isDesktopMode } from '../utils/desktopMode'

const { Title, Text } = Typography
const { Option } = Select

interface FirstRunWizardProps {
  onComplete: () => void
}

interface ConfigForm {
  // 语音识别配置
  speechMethod: string
  whisperModel: string
  openaiApiKey: string
  
  // LLM配置
  llmProvider: string
  llmApiKey: string
  azureApiKey?: string
  azureRegion?: string
  googleApiKey?: string
  aliyunApiKey?: string
  customApiKey?: string
  customEndpoint?: string
}

const FirstRunWizard: React.FC<FirstRunWizardProps> = ({ onComplete }) => {
  const [currentStep, setCurrentStep] = useState(0)
  const [loading, setLoading] = useState(false)
  const [form] = Form.useForm<ConfigForm>()
  
  const [config, setConfig] = useState<ConfigForm>({
    speechMethod: 'whisper_local',
    whisperModel: 'base',
    openaiApiKey: '',
    llmProvider: 'dashscope',
    llmApiKey: ''
  })

  // 确保表单在组件挂载时正确初始化
  useEffect(() => {
    form.setFieldsValue(config)
    console.log('表单初始化完成，初始值:', config)
  }, [form])

  const handleNext = () => {
    if (currentStep === 0) {
      // 验证第一步的配置
      const values = form.getFieldsValue()
      console.log('下一步按钮点击 - 表单值:', values)
      console.log('llmProvider:', values.llmProvider)
      console.log('llmApiKey:', values.llmApiKey)
      
      if (!values.llmProvider || !values.llmApiKey || values.llmApiKey.trim() === '') {
        message.error('请选择LLM提供商并输入API Key')
        return
      }
      setConfig({ ...config, ...values })
      setCurrentStep(1)
    } else {
      handleComplete()
    }
  }

  const handleComplete = async () => {
    setLoading(true)
    try {
      const values = form.getFieldsValue()
      const finalConfig = { ...config, ...values }
      
      // 验证语音识别配置
      if (!finalConfig.speechMethod) {
        message.error('请选择语音识别方案')
        setLoading(false)
        return
      }
      
      // 只有当用户输入了API key时才保存LLM配置
      if (finalConfig.llmApiKey && finalConfig.llmApiKey.trim()) {
        try {
          await saveLLMConfig(finalConfig)
          console.log('LLM配置保存成功')
        } catch (error) {
          console.error('LLM配置保存失败:', error)
          message.error('LLM配置保存失败，请重试')
          setLoading(false)
          return
        }
      }
      
      // 保存语音识别配置 - 添加错误处理
      try {
        await saveSpeechConfig(finalConfig)
      } catch (error) {
        console.warn('语音识别配置保存失败，使用默认配置:', error)
        // 不抛出错误，允许用户继续完成向导
      }
      
      // 如果是本地Whisper，下载模型
      if (finalConfig.speechMethod === 'whisper_local') {
        await downloadWhisperModel(finalConfig.whisperModel)
      }
      
      // 配置保存完成，直接进入工具首页
      message.success('配置完成!欢迎使用AutoClip')
      onComplete()
    } catch (error) {
      console.error('配置保存失败:', error)
      const errorMessage = error instanceof Error ? error.message : '配置保存失败,请重试'
      message.error(`配置保存失败: ${errorMessage}`)
    } finally {
      setLoading(false)
    }
  }

  // 跳过当前步骤，稍后设置
  const handleSkip = async () => {
    if (currentStep === 0) {
      // 跳过AI模型配置，进入语音识别配置
      setCurrentStep(1)
      message.info('已跳过AI模型配置,请稍后在配置页中进行设置', 3)
    } else {
      // 跳过语音识别配置，完成向导
      // 确保不保存任何空的API配置
      try {
        // 只保存语音识别配置，不保存LLM配置
        const values = form.getFieldsValue()
        const finalConfig = { ...config, ...values }
        try {
          await saveSpeechConfig(finalConfig)
        } catch (error) {
          console.warn('语音识别配置保存失败，使用默认配置:', error)
        }
        
        message.info('已跳过语音识别配置,请稍后在配置页中进行设置', 3)
        onComplete()
      } catch (error) {
        message.error('配置保存失败,请重试')
        console.error('配置保存失败:', error)
      }
    }
  }

  const saveLLMConfig = async (config: ConfigForm) => {
    try {
      // 在Web模式下也允许保存配置，用于测试和开发
      const isDesktop = await isDesktopMode()
      console.log('桌面模式检测结果:', isDesktop)

      console.log('开始保存LLM配置:', {
        provider: config.llmProvider,
        apiKeyLength: config.llmApiKey?.length || 0
      })

      // 先获取现有配置，避免清空已有的API key
      let existingSettings = null
      try {
        existingSettings = await settingsApi.getSettings()
      } catch (error) {
        console.warn('获取现有配置失败，将使用默认配置:', error)
      }

      // 获取现有的API keys，只更新当前提供商的key
      const existingApiKeys = existingSettings?.api?.api_keys || {}
      
      const settings = {
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
            // 只更新当前提供商的API key，保持其他提供商的值
            dashscope: config.llmProvider === 'dashscope' ? config.llmApiKey : (existingApiKeys.dashscope || ''),
            openai: config.llmProvider === 'openai' ? config.llmApiKey : (existingApiKeys.openai || ''),
            gemini: config.llmProvider === 'gemini' ? config.llmApiKey : (existingApiKeys.gemini || ''),
            siliconflow: config.llmProvider === 'siliconflow' ? config.llmApiKey : (existingApiKeys.siliconflow || ''),
            jimeng_access: existingApiKeys.jimeng_access || '',
            jimeng_secret: existingApiKeys.jimeng_secret || ''
          },
          api_model: config.llmProvider === 'dashscope' ? 'qwen-plus' : 
                     config.llmProvider === 'openai' ? 'gpt-3.5-turbo' :
                     config.llmProvider === 'gemini' ? 'gemini-pro' : 'qwen-plus',
          api_max_tokens: 4000,
          api_timeout: 30
        },
        processing: {
          processing_chunk_size: 5000,
          processing_min_score: 0.7,
          processing_max_clips: 5,
          processing_max_retries: 3
        },
        logs: {
          log_level: "INFO",
          log_file_path: "",
          log_file_max_size: 10,
          log_file_backup_count: 5
        }
      }
      
      console.log('发送设置到后端:', settings)
      const result = await settingsApi.updateSettings(settings)
      console.log('LLM配置保存成功，后端响应:', result)
    } catch (error) {
      console.error('LLM配置保存失败:', error)
      const detail = error instanceof Error ? error.message : '未知错误'
      throw new Error(`LLM配置保存失败: ${detail}`)
    }
  }

  const saveSpeechConfig = async (config: ConfigForm) => {
    try {
      // 检查是否在桌面模式
      const isDesktop = await isDesktopMode()
      if (!isDesktop) {
        console.warn('非桌面模式，跳过语音配置保存')
        return
      }

      const values = form.getFieldsValue()
      const speechConfig = {
        method: config.speechMethod,
        whisper_config: {
          model_name: config.whisperModel || 'base',
          language: 'auto',
          enable_timestamps: true,
          enable_punctuation: true
        },
        openai_config: {
          api_key: values.openaiApiKey || '',
          language: 'auto',
          enable_timestamps: true
        },
        azure_config: {
          api_key: values.azureApiKey || '',
          region: values.azureRegion || '',
          language: 'auto',
          enable_timestamps: true,
          enable_punctuation: true
        },
        google_config: {
          api_key: values.googleApiKey || '',
          language: 'auto',
          enable_timestamps: true,
          enable_punctuation: true
        },
        aliyun_config: {
          api_key: values.aliyunApiKey || '',
          language: 'auto',
          enable_timestamps: true,
          enable_punctuation: true
        },
        custom_api_config: {
          api_key: values.customApiKey || '',
          endpoint: values.customEndpoint || '',
          language: 'auto',
          enable_timestamps: true,
          enable_punctuation: true
        },
        enable_fallback: true,
        fallback_method: 'whisper_local',
        output_format: 'srt'
      }
      
      const response = await fetch('/api/v1/speech-recognition/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(speechConfig)
      })
      
      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`语音识别配置保存失败: ${response.status} ${errorText}`)
      }
      
      console.log('语音识别配置保存成功')
    } catch (error) {
      console.error('语音识别配置保存失败:', error)
      if (error instanceof Error) {
        throw new Error(`语音识别配置保存失败: ${error.message}`)
      } else {
        throw new Error('语音识别配置保存失败')
      }
    }
  }

  const downloadWhisperModel = async (modelName: string) => {
    try {
      const response = await fetch('/api/v1/speech-recognition/whisper-models/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelName })
      })
      
      if (!response.ok) {
        throw new Error('模型下载失败')
      }
    } catch (error) {
      console.error('Whisper模型下载失败:', error)
      // 不阻止向导完成
    }
  }


  const testApiConnection = async (provider: string, apiKey: string) => {
    // 从表单中获取最新的API Key值
    const formValues = form.getFieldsValue()
    const currentApiKey = formValues.llmApiKey || apiKey
    
    console.log('testApiConnection 调用参数:', { provider, apiKey })
    console.log('testApiConnection 表单值:', formValues)
    console.log('testApiConnection 当前API Key:', currentApiKey)
    
    if (!currentApiKey || currentApiKey.trim() === '') {
      message.warning('请先输入API Key')
      return
    }
    
    try {
      const response = await fetch('/api/v1/settings/test-api', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, api_key: currentApiKey })
      })
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const result = await response.json()
      if (result.success) {
        message.success('API连接测试成功!')
      } else {
        message.error(`API连接测试失败: ${result.error || '未知错误'}`)
      }
    } catch (error) {
      console.error('API测试错误:', error)
      const detail = error instanceof Error ? error.message : '网络错误'
      message.error(`API连接测试失败: ${detail}`)
    }
  }

  // 获取API Key获取方式的智能提示
  const getApiKeyHelp = (provider: string) => {
    const helpMap: Record<string, { name: string; url: string; description: string }> = {
      dashscope: {
        name: '阿里云通义千问',
        url: 'https://dashscope.aliyun.com',
        description: '注册阿里云账号,开通DashScope服务,创建API Key'
      },
      openai: {
        name: 'OpenAI',
        url: 'https://platform.openai.com',
        description: '注册OpenAI账号,在API Keys页面创建新的密钥'
      },
      gemini: {
        name: 'Google Gemini',
        url: 'https://makersuite.google.com',
        description: '使用Google账号登录,在API Keys页面创建密钥'
      },
      siliconflow: {
        name: 'SiliconFlow',
        url: 'https://cloud.siliconflow.cn',
        description: '注册SiliconFlow账号,在控制台创建API Key'
      }
    }
    return helpMap[provider] || helpMap.dashscope
  }

  return (
    <div style={{ 
      maxWidth: '600px', 
      margin: '0 auto', 
      padding: '24px 16px',
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center'
    }}>
      {/* 头部标题区域 - 更紧凑 */}
      <div style={{ textAlign: 'center', marginBottom: '24px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <img src="/favicon.png" alt="AutoClip" style={{ width: 40, height: 40, marginBottom: '8px', display: 'block' }} />
        <Title level={2} style={{ color: '#1890ff', marginBottom: '8px' }}>
          欢迎使用 AutoClip
        </Title>
        <Text type="secondary" style={{ fontSize: '14px' }}>
          让我们快速配置您的AI视频切片工具
        </Text>
      </div>

      {/* 主配置卡片 - 更紧凑的间距 */}
      <Card style={{ marginBottom: '16px' }}>
        {/* 步骤标题 - 更紧凑 */}
        <div style={{ textAlign: 'center', marginBottom: '20px' }}>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            gap: '8px',
            marginBottom: '4px'
          }}>
            {currentStep === 0 ? <ApiOutlined style={{ color: '#1890ff' }} /> : <SoundOutlined style={{ color: '#1890ff' }} />}
            <Title level={4} style={{ margin: 0 }}>
              {currentStep === 0 ? '配置AI模型' : '配置语音识别'}
            </Title>
          </div>
          <Text type="secondary" style={{ fontSize: '12px' }}>
            {currentStep === 0 
              ? '选择大语言模型提供商并输入API Key' 
              : '选择语音识别方案'
            }
          </Text>
        </div>

        <Form 
          form={form} 
          layout="vertical" 
          initialValues={config}
          onValuesChange={(changedValues, allValues) => {
            console.log('表单值变化:', { changedValues, allValues })
          }}
        >
          {currentStep === 0 ? (
            // LLM配置步骤 - 更紧凑的布局
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Form.Item
                name="llmProvider"
                label="选择AI模型提供商"
                rules={[{ required: true, message: '请选择AI模型提供商' }]}
                style={{ marginBottom: '12px' }}
              >
                <Select size="middle" placeholder="选择提供商">
                  <Option value="dashscope">
                    <Space>
                      <Text strong>阿里云通义千问</Text>
                      <Text type="secondary">(推荐国内用户)</Text>
                    </Space>
                  </Option>
                  <Option value="openai">
                    <Space>
                      <Text strong>OpenAI GPT</Text>
                      <Text type="secondary">(需要科学上网)</Text>
                    </Space>
                  </Option>
                  <Option value="gemini">
                    <Space>
                      <Text strong>Google Gemini</Text>
                      <Text type="secondary">(需要科学上网)</Text>
                    </Space>
                  </Option>
                  <Option value="siliconflow">
                    <Space>
                      <Text strong>SiliconFlow</Text>
                      <Text type="secondary">(国内替代方案)</Text>
                    </Space>
                  </Option>
                </Select>
              </Form.Item>

              {/* API Key输入框和测试按钮 - 水平布局 */}
              <Form.Item
                name="llmApiKey"
                label="API Key"
                rules={[{ required: true, message: '请输入API Key' }]}
                style={{ marginBottom: '12px' }}
              >
                <div style={{ display: 'flex', gap: '8px' }}>
                  <Input.Password 
                    size="middle" 
                    placeholder="请输入您的API Key"
                    style={{ 
                      flex: 1,
                      backgroundColor: '#fafafa',
                      borderColor: '#d9d9d9'
                    }}
                  />
                  <Button 
                    type="default"
                    size="middle"
                    onClick={() => {
                      const values = form.getFieldsValue()
                      console.log('测试按钮点击 - 表单值:', values)
                      testApiConnection(values.llmProvider || 'dashscope', values.llmApiKey || '')
                    }}
                    style={{ width: '80px' }}
                    icon={<LinkOutlined />}
                  >
                    测试
                  </Button>
                </div>
              </Form.Item>

              {/* 智能API Key获取方式提示 */}
              <Form.Item shouldUpdate={(prevValues, currentValues) => prevValues.llmProvider !== currentValues.llmProvider}>
                {({ getFieldValue }) => {
                  const provider = getFieldValue('llmProvider') || 'dashscope'
                  const help = getApiKeyHelp(provider)
                  return (
                    <Alert
                      message={
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <InfoCircleOutlined />
                          <span>{help.name} API Key获取方式</span>
                        </div>
                      }
                      description={
                        <div>
                          <p style={{ margin: '4px 0', fontSize: '12px' }}>{help.description}</p>
                          <p style={{ margin: '4px 0', fontSize: '12px' }}>
                            访问: <ExternalLink url={help.url} text={help.url} />
                          </p>
                        </div>
                      }
                      type="info"
                      showIcon={false}
                      style={{ fontSize: '12px' }}
                    />
                  )
                }}
              </Form.Item>
            </Space>
          ) : (
            // 语音识别配置步骤 - 更紧凑的布局
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Form.Item
                name="speechMethod"
                label="选择语音识别方案"
                rules={[{ required: true, message: '请选择语音识别方案' }]}
                style={{ marginBottom: '12px' }}
              >
                <Select size="middle" placeholder="选择方案">
                  <Option value="whisper_local">
                    <Space>
                      <span>🆓</span>
                      <Text strong>本地 Whisper 模型</Text>
                      <Text type="secondary">(免费离线，推荐新手)</Text>
                    </Space>
                  </Option>
                  <Option value="openai_api">
                    <Space>
                      <span>🤖</span>
                      <Text strong>OpenAI Whisper API</Text>
                      <Text type="secondary">(云端处理，准确度更高)</Text>
                    </Space>
                  </Option>
                  <Option value="azure_speech">
                    <Space>
                      <span>☁️</span>
                      <Text strong>Azure Speech Services</Text>
                      <Text type="secondary">(企业级服务)</Text>
                    </Space>
                  </Option>
                  <Option value="google_speech">
                    <Space>
                      <span>🌐</span>
                      <Text strong>Google Speech-to-Text</Text>
                      <Text type="secondary">(多语言支持)</Text>
                    </Space>
                  </Option>
                  <Option value="aliyun_speech">
                    <Space>
                      <span>☁️</span>
                      <Text strong>阿里云语音识别</Text>
                      <Text type="secondary">(中文优化)</Text>
                    </Space>
                  </Option>
                  <Option value="custom_api">
                    <Space>
                      <span>⚙️</span>
                      <Text strong>自定义API</Text>
                      <Text type="secondary">(自定义服务端点)</Text>
                    </Space>
                  </Option>
                </Select>
              </Form.Item>

              <Form.Item shouldUpdate={(prevValues, currentValues) => prevValues.speechMethod !== currentValues.speechMethod} noStyle>
                {({ getFieldValue }) => {
                  const speechMethod = getFieldValue('speechMethod')
                  
                  if (speechMethod === 'whisper_local') {
                    return (
                      <Form.Item
                        name="whisperModel"
                        label="选择模型大小"
                        style={{ marginBottom: '12px' }}
                      >
                        <Select size="middle" placeholder="选择模型">
                          <Option value="tiny">Tiny (39MB) - 最快速度</Option>
                          <Option value="base">Base (74MB) - 平衡选择 (推荐)</Option>
                          <Option value="small">Small (244MB) - 较好准确度</Option>
                          <Option value="medium">Medium (769MB) - 高准确度</Option>
                          <Option value="large">Large (1550MB) - 最高准确度</Option>
                        </Select>
                      </Form.Item>
                    )
                  }
                  
                  if (speechMethod === 'openai_api') {
                    return (
                      <Form.Item
                        name="openaiApiKey"
                        label="OpenAI API Key"
                        rules={[{ required: true, message: '请输入OpenAI API Key' }]}
                        style={{ marginBottom: '12px' }}
                      >
                        <Input.Password 
                          size="middle" 
                          placeholder="请输入OpenAI API Key"
                        />
                      </Form.Item>
                    )
                  }
                  
                  if (speechMethod === 'azure_speech') {
                    return (
                      <Space direction="vertical" size="small" style={{ width: '100%' }}>
                        <Form.Item
                          name="azureApiKey"
                          label="Azure API Key"
                          rules={[{ required: true, message: '请输入Azure API Key' }]}
                          style={{ marginBottom: '8px' }}
                        >
                          <Input.Password 
                            size="middle" 
                            placeholder="请输入Azure Speech API Key"
                          />
                        </Form.Item>
                        <Form.Item
                          name="azureRegion"
                          label="Azure 区域"
                          style={{ marginBottom: '12px' }}
                        >
                          <Input 
                            size="middle" 
                            placeholder="例如: eastus, westus2"
                          />
                        </Form.Item>
                      </Space>
                    )
                  }
                  
                  if (speechMethod === 'google_speech') {
                    return (
                      <Form.Item
                        name="googleApiKey"
                        label="Google API Key"
                        rules={[{ required: true, message: '请输入Google API Key' }]}
                        style={{ marginBottom: '12px' }}
                      >
                        <Input.Password 
                          size="middle" 
                          placeholder="请输入Google Speech-to-Text API Key"
                        />
                      </Form.Item>
                    )
                  }
                  
                  if (speechMethod === 'aliyun_speech') {
                    return (
                      <Form.Item
                        name="aliyunApiKey"
                        label="阿里云 API Key"
                        rules={[{ required: true, message: '请输入阿里云 API Key' }]}
                        style={{ marginBottom: '12px' }}
                      >
                        <Input.Password 
                          size="middle" 
                          placeholder="请输入阿里云语音识别 API Key"
                        />
                      </Form.Item>
                    )
                  }
                  
                  if (speechMethod === 'custom_api') {
                    return (
                      <Space direction="vertical" size="small" style={{ width: '100%' }}>
                        <Form.Item
                          name="customApiKey"
                          label="自定义 API Key"
                          rules={[{ required: true, message: '请输入自定义 API Key' }]}
                          style={{ marginBottom: '8px' }}
                        >
                          <Input.Password 
                            size="middle" 
                            placeholder="请输入自定义 API Key"
                          />
                        </Form.Item>
                        <Form.Item
                          name="customEndpoint"
                          label="API 端点"
                          rules={[{ required: true, message: '请输入API端点' }]}
                          style={{ marginBottom: '12px' }}
                        >
                          <Input 
                            size="middle" 
                            placeholder="例如: https://api.example.com/speech"
                          />
                        </Form.Item>
                      </Space>
                    )
                  }
                  
                  return null
                }}
              </Form.Item>

              {/* 智能配置说明 - 根据选择的方案显示对应说明 */}
              <Form.Item shouldUpdate={(prevValues, currentValues) => prevValues.speechMethod !== currentValues.speechMethod} style={{ marginBottom: '8px' }}>
                {({ getFieldValue }) => {
                  const speechMethod = getFieldValue('speechMethod')
                  
                  const getMethodDescription = (method: string) => {
                    const descriptions: Record<string, { icon: string; name: string; description: string }> = {
                      whisper_local: {
                        icon: '🆓',
                        name: '本地 Whisper 模型',
                        description: '免费离线使用，首次使用会自动下载模型，后续无需网络连接。推荐新手用户使用。'
                      },
                      openai_api: {
                        icon: '🤖',
                        name: 'OpenAI Whisper API',
                        description: '云端处理，识别准确度更高，按使用量计费。需要稳定的网络连接。'
                      },
                      azure_speech: {
                        icon: '☁️',
                        name: 'Azure Speech Services',
                        description: '企业级语音识别服务，支持多种语言和方言，适合商业使用。'
                      },
                      google_speech: {
                        icon: '🌐',
                        name: 'Google Speech-to-Text',
                        description: '多语言支持，识别准确度高，支持实时语音识别。'
                      },
                      aliyun_speech: {
                        icon: '☁️',
                        name: '阿里云语音识别',
                        description: '中文优化，国内访问速度快，支持多种中文方言识别。'
                      },
                      custom_api: {
                        icon: '⚙️',
                        name: '自定义API',
                        description: '支持自定义服务端点，可以接入自己的语音识别服务。'
                      }
                    }
                    return descriptions[method] || descriptions.whisper_local
                  }
                  
                  const methodInfo = getMethodDescription(speechMethod)
                  
                  return (
                    <Alert
                      message={
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span>{methodInfo.icon}</span>
                          <span>{methodInfo.name} 配置说明</span>
                        </div>
                      }
                      description={
                        <div style={{ fontSize: '12px' }}>
                          <p style={{ margin: '4px 0' }}>{methodInfo.description}</p>
                        </div>
                      }
                      type="info"
                      showIcon={false}
                      style={{ fontSize: '12px', marginTop: '8px' }}
                    />
                  )
                }}
              </Form.Item>
            </Space>
          )}
        </Form>
      </Card>

      {/* 底部按钮区域 - 移除步骤指示器，统一按钮样式 */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: '12px'
      }}>
        <div>
          {currentStep > 0 && (
            <Button 
              size="middle"
              onClick={() => setCurrentStep(0)}
              disabled={loading}
            >
              上一步
            </Button>
          )}
        </div>
        
        <div style={{ display: 'flex', gap: '8px' }}>
          <Button 
            type="default"
            size="middle"
            onClick={handleSkip}
            disabled={loading}
          >
            稍后设置
          </Button>
          <Button 
            type="primary" 
            size="middle"
            onClick={handleNext}
            loading={loading}
            icon={loading ? <LoadingOutlined /> : <CheckCircleOutlined />}
          >
            {currentStep === 0 ? '下一步' : '开始使用'}
          </Button>
        </div>
      </div>

      {loading && (
        <div style={{ 
          textAlign: 'center', 
          marginTop: '20px',
          padding: '20px',
          background: '#f5f5f5',
          borderRadius: '8px'
        }}>
          <LoadingOutlined style={{ fontSize: '24px', marginRight: '8px' }} />
          <Text>正在保存配置并创建示例项目...</Text>
        </div>
      )}
    </div>
  )
}

export default FirstRunWizard