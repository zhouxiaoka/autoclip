import React, { useState, useEffect } from 'react'
import { 
  Layout, 
  Card, 
  Button, 
  Typography, 
  Space, 
  Alert, 
  Row, 
  Col, 
  Form, 
  Input, 
  message,
  Tag,
  Descriptions,
  Collapse
} from 'antd'
import { 
  BugOutlined, 
  ApiOutlined, 
  SettingOutlined, 
  CheckCircleOutlined,
  CloseCircleOutlined,
  ReloadOutlined
} from '@ant-design/icons'
import { settingsApi } from '../services/api'
import { isDesktopMode } from '../utils/desktopMode'

const { Content } = Layout
const { Title, Text, Paragraph } = Typography
const { Panel } = Collapse

interface DebugInfo {
  desktopMode: {
    isDesktop: boolean
    source: string
    environment?: any
  }
  apiStatus: {
    settings: boolean
    desktopMode: boolean
    testApi: boolean
  }
  currentSettings: any
  errors: string[]
}

const DebugPage: React.FC = () => {
  const [loading, setLoading] = useState(false)
  const [debugInfo, setDebugInfo] = useState<DebugInfo>({
    desktopMode: { isDesktop: false, source: 'unknown' },
    apiStatus: { settings: false, desktopMode: false, testApi: false },
    currentSettings: null,
    errors: []
  })
  const [form] = Form.useForm()

  // 测试桌面模式检测
  const testDesktopMode = async () => {
    try {
      setLoading(true)
      const isDesktop = await isDesktopMode()
      const info = {
        isDesktop,
        source: 'frontend_check',
        environment: {
          userAgent: navigator.userAgent,
          hasTauri: Boolean((window as any).__TAURI__ || (window as any).__TAURI_INTERNALS__),
          location: window.location.href,
        }
      }
      setDebugInfo(prev => ({
        ...prev,
        desktopMode: info
      }))
      message.success('桌面模式检测完成')
    } catch (error: any) {
      const errorMsg = `桌面模式检测失败: ${error.message}`
      setDebugInfo(prev => ({
        ...prev,
        errors: [...prev.errors, errorMsg]
      }))
      message.error(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  // 测试API连接
  const testApiConnections = async () => {
    const errors: string[] = []
    const apiStatus = { settings: false, desktopMode: false, testApi: false }

    try {
      setLoading(true)
      
      // 测试设置API
      try {
        const settings = await settingsApi.getSettings()
        apiStatus.settings = true
        setDebugInfo(prev => ({
          ...prev,
          currentSettings: settings
        }))
      } catch (error: any) {
        errors.push(`设置API失败: ${error.message}`)
      }

      // 测试桌面模式API
      try {
        const desktopMode = await settingsApi.checkDesktopMode()
        apiStatus.desktopMode = true
        console.log('桌面模式API响应:', desktopMode)
      } catch (error: any) {
        errors.push(`桌面模式API失败: ${error.message}`)
      }

      // 测试API Key测试接口
      try {
        const testResult = await settingsApi.testApiKey('dashscope', 'test-key')
        apiStatus.testApi = true
        console.log('API测试响应:', testResult)
      } catch (error: any) {
        errors.push(`API测试接口失败: ${error.message}`)
      }

      setDebugInfo(prev => ({
        ...prev,
        apiStatus,
        errors: [...prev.errors, ...errors]
      }))

      if (errors.length === 0) {
        message.success('所有API连接测试通过')
      } else {
        message.warning(`部分API测试失败: ${errors.length}个错误`)
      }
    } catch (error: any) {
      const errorMsg = `API连接测试失败: ${error.message}`
      setDebugInfo(prev => ({
        ...prev,
        errors: [...prev.errors, errorMsg]
      }))
      message.error(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  // 测试API Key保存
  const testApiKeySave = async () => {
    try {
      setLoading(true)
      const values = form.getFieldsValue()
      
      if (!values.apiKey || !values.provider) {
        message.error('请填写API Key和提供商')
        return
      }

      const testSettings = {
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
            dashscope: values.provider === 'dashscope' ? values.apiKey : '',
            openai: values.provider === 'openai' ? values.apiKey : '',
            gemini: values.provider === 'gemini' ? values.apiKey : '',
            siliconflow: values.provider === 'siliconflow' ? values.apiKey : '',
            jimeng_access: '',
            jimeng_secret: ''
          },
          api_model: values.provider === 'dashscope' ? 'qwen-plus' : 
                     values.provider === 'openai' ? 'gpt-3.5-turbo' :
                     values.provider === 'gemini' ? 'gemini-pro' : 'qwen-plus',
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
          log_retention_days: 7
        }
      }

      await settingsApi.updateSettings(testSettings)
      message.success('API Key保存测试成功！')
    } catch (error: any) {
      const errorMsg = `API Key保存失败: ${error.message}`
      setDebugInfo(prev => ({
        ...prev,
        errors: [...prev.errors, errorMsg]
      }))
      message.error(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  // 清除缓存并重新检测
  const refreshAll = async () => {
    await testDesktopMode()
    await testApiConnections()
  }

  // 页面加载时自动检测
  useEffect(() => {
    testDesktopMode()
    testApiConnections()
  }, [])

  return (
    <Layout style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <Content style={{ padding: '24px' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
          <Title level={2}>
            <BugOutlined /> AutoClip 调试页面
          </Title>
          
          <Paragraph>
            这个页面用于调试桌面模式检测和API Key保存功能。请按顺序测试各个功能。
          </Paragraph>

          <Row gutter={[16, 16]}>
            {/* 桌面模式检测 */}
            <Col span={24}>
              <Card title="桌面模式检测" extra={
                <Space>
                  <Button 
                    icon={<ReloadOutlined />} 
                    onClick={testDesktopMode}
                    loading={loading}
                  >
                    重新检测
                  </Button>
                  <Button 
                    icon={<ReloadOutlined />} 
                    onClick={refreshAll}
                    loading={loading}
                  >
                    刷新全部
                  </Button>
                </Space>
              }>
                <Descriptions bordered column={2}>
                  <Descriptions.Item label="桌面模式状态">
                    <Tag color={debugInfo.desktopMode.isDesktop ? 'green' : 'red'}>
                      {debugInfo.desktopMode.isDesktop ? '是' : '否'}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="检测来源">
                    <Tag color="blue">{debugInfo.desktopMode.source}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="环境信息" span={2}>
                    <pre style={{ margin: 0, fontSize: '12px' }}>
                      {JSON.stringify(debugInfo.desktopMode.environment, null, 2)}
                    </pre>
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            </Col>

            {/* API连接测试 */}
            <Col span={24}>
              <Card title="API连接测试" extra={
                <Button 
                  icon={<ApiOutlined />} 
                  onClick={testApiConnections}
                  loading={loading}
                >
                  测试连接
                </Button>
              }>
                <Row gutter={16}>
                  <Col span={8}>
                    <Card size="small">
                      <Space>
                        {debugInfo.apiStatus.settings ? 
                          <CheckCircleOutlined style={{ color: 'green' }} /> : 
                          <CloseCircleOutlined style={{ color: 'red' }} />
                        }
                        <Text>设置API</Text>
                      </Space>
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card size="small">
                      <Space>
                        {debugInfo.apiStatus.desktopMode ? 
                          <CheckCircleOutlined style={{ color: 'green' }} /> : 
                          <CloseCircleOutlined style={{ color: 'red' }} />
                        }
                        <Text>桌面模式API</Text>
                      </Space>
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card size="small">
                      <Space>
                        {debugInfo.apiStatus.testApi ? 
                          <CheckCircleOutlined style={{ color: 'green' }} /> : 
                          <CloseCircleOutlined style={{ color: 'red' }} />
                        }
                        <Text>API测试接口</Text>
                      </Space>
                    </Card>
                  </Col>
                </Row>
              </Card>
            </Col>

            {/* API Key保存测试 */}
            <Col span={24}>
              <Card title="API Key保存测试" extra={
                <Button 
                  type="primary"
                  icon={<SettingOutlined />} 
                  onClick={testApiKeySave}
                  loading={loading}
                >
                  测试保存
                </Button>
              }>
                <Form form={form} layout="vertical">
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item
                        name="provider"
                        label="API提供商"
                        rules={[{ required: true, message: '请选择提供商' }]}
                      >
                        <Input placeholder="dashscope, openai, gemini, siliconflow" />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item
                        name="apiKey"
                        label="API Key"
                        rules={[{ required: true, message: '请输入API Key' }]}
                      >
                        <Input.Password placeholder="请输入API Key" />
                      </Form.Item>
                    </Col>
                  </Row>
                </Form>
              </Card>
            </Col>

            {/* 当前设置信息 */}
            {debugInfo.currentSettings && (
              <Col span={24}>
                <Card title="当前设置信息">
                  <Collapse>
                    <Panel header="查看完整设置" key="1">
                      <pre style={{ 
                        background: '#f5f5f5', 
                        padding: '16px', 
                        borderRadius: '4px',
                        fontSize: '12px',
                        maxHeight: '400px',
                        overflow: 'auto'
                      }}>
                        {JSON.stringify(debugInfo.currentSettings, null, 2)}
                      </pre>
                    </Panel>
                  </Collapse>
                </Card>
              </Col>
            )}

            {/* 错误信息 */}
            {debugInfo.errors.length > 0 && (
              <Col span={24}>
                <Card title="错误信息" style={{ borderColor: '#ff4d4f' }}>
                  {debugInfo.errors.map((error, index) => (
                    <Alert
                      key={index}
                      message={error}
                      type="error"
                      showIcon
                      style={{ marginBottom: '8px' }}
                    />
                  ))}
                </Card>
              </Col>
            )}

            {/* 使用说明 */}
            <Col span={24}>
              <Card title="使用说明">
                <Alert
                  message="调试步骤"
                  description={
                    <div>
                      <p>1. 首先检查"桌面模式检测"是否显示为"是"</p>
                      <p>2. 然后测试"API连接测试"，确保所有连接都显示绿色</p>
                      <p>3. 最后在"API Key保存测试"中输入真实的API Key进行测试</p>
                      <p>4. 如果出现错误，请查看"错误信息"部分</p>
                    </div>
                  }
                  type="info"
                  showIcon
                />
              </Card>
            </Col>
          </Row>
        </div>
      </Content>
    </Layout>
  )
}

export default DebugPage