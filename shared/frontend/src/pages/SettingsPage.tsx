import React, { useState, useEffect } from 'react'
import { Layout, Card, Form, Input, Button, message, Typography, Space, Alert, Divider, Row, Col, Spin } from 'antd'
import { KeyOutlined, SaveOutlined, SettingOutlined, InfoCircleOutlined } from '@ant-design/icons'
import { settingsApi } from '../services/api'
import './SettingsPage.css'

const { Content } = Layout
const { Title, Text, Paragraph } = Typography

interface BrowserInfo {
  name: string
  value: string
  available: boolean
  priority: number
}

interface ApiSettings {
  dashscope_api_key: string
  model_name: string
  chunk_size: number
  min_score_threshold: number
  max_clips_per_collection: number
  default_browser?: string
}

const SettingsPage: React.FC = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [availableBrowsers, setAvailableBrowsers] = useState<BrowserInfo[]>([])
  const [detectingBrowsers, setDetectingBrowsers] = useState(false)
  const [selectedBrowser, setSelectedBrowser] = useState<string>('')

  useEffect(() => {
    loadSettings()
    detectAvailableBrowsers()
  }, [])

  // 检测可用浏览器
  const detectAvailableBrowsers = async () => {
    setDetectingBrowsers(true)
    try {
      const response = await fetch('http://localhost:8000/api/browsers/detect')
      if (response.ok) {
        const data = await response.json()
        const browsers: BrowserInfo[] = data.browsers
        setAvailableBrowsers(browsers)
        
        // 自动选择第一个可用的浏览器，优先选择Chrome
        const chromeBrowser = browsers.find(b => b.value === 'chrome' && b.available)
        const firstAvailable = chromeBrowser || browsers.find(b => b.available)
        if (firstAvailable) {
          form.setFieldValue('default_browser', firstAvailable.value)
          setSelectedBrowser(firstAvailable.value)
        }
      } else {
        // 如果API调用失败，使用默认配置
        const browsers: BrowserInfo[] = [
          { name: 'Chrome', value: 'chrome', available: true, priority: 1 },
          { name: 'Edge', value: 'edge', available: true, priority: 2 },
          { name: 'Firefox', value: 'firefox', available: true, priority: 3 },
          { name: 'Safari', value: 'safari', available: true, priority: 4 }
        ]
        setAvailableBrowsers(browsers)
        form.setFieldValue('default_browser', 'chrome')
        setSelectedBrowser('chrome')
      }
    } catch (error) {
      console.error('检测浏览器失败:', error)
      // 使用默认配置
      const browsers: BrowserInfo[] = [
        { name: 'Chrome', value: 'chrome', available: true, priority: 1 },
        { name: 'Edge', value: 'edge', available: true, priority: 2 },
        { name: 'Firefox', value: 'firefox', available: true, priority: 3 },
        { name: 'Safari', value: 'safari', available: true, priority: 4 }
      ]
      setAvailableBrowsers(browsers)
      form.setFieldValue('default_browser', 'chrome')
      setSelectedBrowser('chrome')
    } finally {
      setDetectingBrowsers(false)
    }
  }

  const loadSettings = async () => {
    try {
      const data = await settingsApi.getSettings()
      form.setFieldsValue(data)
      if (data.default_browser) setSelectedBrowser(data.default_browser)
    } catch (error) {
      message.error('加载配置失败')
      console.error('Load settings error:', error)
    }
  }

  const handleSave = async (values: ApiSettings) => {
    setLoading(true)
    try {
      await settingsApi.updateSettings(values)
      message.success('配置保存成功')
    } catch (error) {
      message.error('保存配置失败')
      console.error('Save settings error:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Content className="settings-page">
      <div className="settings-container">
        <Title level={2} className="settings-title">
          <SettingOutlined /> 系统配置
        </Title>
        
        <Card title="API 配置" className="settings-card">
          <Alert
            message="配置说明"
            description="请配置通义千问API密钥以启用AI自动切片功能。您可以在阿里云控制台获取API密钥。"
            type="info"
            showIcon
            className="settings-alert"
          />
          
          <Form
            form={form}
            layout="vertical"
            onFinish={handleSave}
            className="settings-form"
            initialValues={{
              model_name: 'qwen-plus',
              chunk_size: 5000,
              min_score_threshold: 0.7,
              max_clips_per_collection: 5
            }}
          >
            <Form.Item
              label="DashScope API Key"
              name="dashscope_api_key"
              className="form-item"
              rules={[
                { required: true, message: '请输入API密钥' },
                { min: 10, message: 'API密钥长度不能少于10位' }
              ]}
            >
              <Input.Password
                placeholder="请输入通义千问API密钥"
                prefix={<KeyOutlined />}
                className="settings-input"
              />
            </Form.Item>

            <Divider className="settings-divider" />

            <Title level={4} className="section-title">模型配置</Title>
            
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  label="模型名称"
                  name="model_name"
                  className="form-item"
                  rules={[{ required: true, message: '请选择模型' }]}
                >
                  <Input placeholder="qwen-plus" className="settings-input" />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  label="文本分块大小"
                  name="chunk_size"
                  className="form-item"
                  rules={[{ required: true, message: '请输入分块大小' }]}
                >
                  <Input 
                    type="number" 
                    placeholder="5000" 
                    addonAfter="字符" 
                    className="settings-input"
                  />
                </Form.Item>
              </Col>
            </Row>

            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  label="最低评分阈值"
                  name="min_score_threshold"
                  className="form-item"
                  rules={[{ required: true, message: '请输入评分阈值' }]}
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
                  label="每个合集最大切片数"
                  name="max_clips_per_collection"
                  className="form-item"
                  rules={[{ required: true, message: '请输入最大切片数' }]}
                >
                  <Input 
                    type="number" 
                    placeholder="5" 
                    addonAfter="个" 
                    className="settings-input"
                  />
                </Form.Item>
              </Col>
            </Row>

            <Divider className="settings-divider" />

            <Title level={4} className="section-title">浏览器配置</Title>
            
            <Alert
              message="B站链接导入设置"
              description="配置默认浏览器用于获取B站登录状态，下载AI字幕。如不配置将只能下载公开字幕。"
              type="info"
              showIcon
              style={{
                background: 'rgba(79, 172, 254, 0.1)',
                border: '1px solid rgba(79, 172, 254, 0.3)',
                borderRadius: '8px',
                marginBottom: '16px'
              }}
            />

            {detectingBrowsers ? (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '12px',
                background: 'rgba(79, 172, 254, 0.1)',
                borderRadius: '8px',
                border: '1px solid rgba(79, 172, 254, 0.3)',
                marginBottom: '16px'
              }}>
                <Spin size="small" />
                <Text style={{ color: '#4facfe', fontSize: '14px' }}>
                  正在检测可用浏览器...
                </Text>
              </div>
            ) : (
              <div style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: '8px',
                marginBottom: '16px'
              }}>
                {availableBrowsers.map(browser => {
                  const isSelected = selectedBrowser === browser.value
                  return (
                    <div
                      key={browser.value}
                      onClick={() => {
                        if (!browser.available) return
                        setSelectedBrowser(browser.value)
                        form.setFieldValue('default_browser', browser.value)
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: isSelected 
                          ? '2px solid #4facfe' 
                          : '2px solid rgba(255, 255, 255, 0.1)',
                        background: isSelected 
                          ? 'rgba(79, 172, 254, 0.2)' 
                          : 'rgba(255, 255, 255, 0.05)',
                        color: isSelected ? '#ffffff' : 'rgba(255, 255, 255, 0.8)',
                        cursor: browser.available ? 'pointer' : 'not-allowed',
                        transition: 'all 0.2s ease',
                        fontSize: '13px',
                        fontWeight: isSelected ? 600 : 400,
                        userSelect: 'none',
                        opacity: browser.available ? 1 : 0.5
                      }}
                      onMouseEnter={(e) => {
                        if (!isSelected && browser.available) {
                          e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)'
                          e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.2)'
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!isSelected) {
                          e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)'
                          e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.1)'
                        }
                      }}
                    >
                      {browser.name}
                      {!browser.available && <span style={{ fontSize: '10px', opacity: 0.6 }}> (未安装)</span>}
                    </div>
                  )
                })}
              </div>
            )}

            <Form.Item className="form-item">
              <Button
                type="primary"
                htmlType="submit"
                icon={<SaveOutlined />}
                loading={loading}
                size="large"
                className="save-button"
                onClick={() => {
                  // 保存时同步selectedBrowser和form
                  form.setFieldValue('default_browser', selectedBrowser)
                }}
              >
                保存配置
              </Button>
            </Form.Item>
          </Form>
        </Card>

        <Card title="使用说明" className="settings-card">
          <Space direction="vertical" size="large" className="instructions-space">
            <div className="instruction-item">
              <Title level={5} className="instruction-title">
                <InfoCircleOutlined /> 1. 获取API密钥
              </Title>
              <Paragraph className="instruction-text">
                访问阿里云控制台 → 人工智能 → 通义千问 → API密钥管理，创建新的API密钥
              </Paragraph>
            </div>
            
            <div className="instruction-item">
              <Title level={5} className="instruction-title">
                <InfoCircleOutlined /> 2. 配置参数说明
              </Title>
              <Paragraph className="instruction-text">
                • <Text strong>文本分块大小</Text>：影响处理速度和精度，建议5000字符<br />
                • <Text strong>评分阈值</Text>：只有高于此分数的片段才会被保留<br />
                • <Text strong>合集切片数</Text>：控制每个主题合集包含的片段数量
              </Paragraph>
            </div>
            
          </Space>
        </Card>
      </div>
    </Content>
  )
}

export default SettingsPage