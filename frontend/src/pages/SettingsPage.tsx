import React, { useState, useEffect } from 'react'
import { Layout, Card, Form, Input, Button, message, Typography, Space, Alert, Divider, Row, Col, Tabs } from 'antd'
import { KeyOutlined, SaveOutlined, ApiOutlined, SettingOutlined, InfoCircleOutlined, UploadOutlined } from '@ant-design/icons'
import { settingsApi } from '../services/api'
import BilibiliAccountManager from '../components/BilibiliAccountManager'
import './SettingsPage.css'

const { Content } = Layout
const { Title, Text, Paragraph } = Typography
const { TextArea } = Input
const { TabPane } = Tabs

interface ApiSettings {
  dashscope_api_key: string
  model_name: string
  chunk_size: number
  min_score_threshold: number
  max_clips_per_collection: number
}

const SettingsPage: React.FC = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [testLoading, setTestLoading] = useState(false)
  const [settings, setSettings] = useState<ApiSettings | null>(null)

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      const data = await settingsApi.getSettings()
      setSettings(data)
      form.setFieldsValue(data)
    } catch (error) {
      message.error('加载配置失败')
      console.error('Load settings error:', error)
    }
  }

  const handleSave = async (values: ApiSettings) => {
    setLoading(true)
    try {
      await settingsApi.updateSettings(values)
      setSettings(values)
      message.success('配置保存成功！API密钥已更新')
    } catch (error) {
      message.error('保存配置失败')
      console.error('Save settings error:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleTestConnection = async () => {
    setTestLoading(true)
    try {
      const values = form.getFieldsValue()
      const result = await settingsApi.testApiKey(values.dashscope_api_key)
      if (result.success) {
        message.success('API密钥测试成功')
      } else {
        message.error(`API密钥测试失败: ${result.error}`)
      }
    } catch (error) {
      message.error('测试连接失败')
      console.error('Test connection error:', error)
    } finally {
      setTestLoading(false)
    }
  }

  return (
    <Content className="settings-page">
      <div className="settings-container">
        <Title level={2} className="settings-title">
          <SettingOutlined /> 系统配置
        </Title>
        
        <Tabs defaultActiveKey="api" className="settings-tabs">
          <TabPane 
            tab={<span><ApiOutlined />API配置</span>} 
            key="api"
          >
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
                    allowClear
                  />
                </Form.Item>

                <Form.Item className="form-item">
                  <Button
                    type="default"
                    icon={<ApiOutlined />}
                    onClick={handleTestConnection}
                    loading={testLoading}
                    className="test-button"
                  >
                    测试连接
                  </Button>
                </Form.Item>

                <Divider className="settings-divider" />

                <Title level={4} className="section-title">模型配置</Title>
                
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      label="模型名称"
                      name="model_name"
                      className="form-item"
                    >
                      <Input 
                        placeholder="qwen-plus" 
                        className="settings-input"
                      />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      label="文本分块大小"
                      name="chunk_size"
                      className="form-item"
                    >
                      <Input 
                        type="number"
                        placeholder="5000" 
                        className="settings-input"
                      />
                    </Form.Item>
                  </Col>
                </Row>

                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      label="评分阈值"
                      name="min_score_threshold"
                      className="form-item"
                    >
                      <Input 
                        type="number"
                        step="0.1"
                        placeholder="0.7" 
                        className="settings-input"
                      />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      label="合集切片数"
                      name="max_clips_per_collection"
                      className="form-item"
                    >
                      <Input 
                        type="number"
                        placeholder="5" 
                        className="settings-input"
                      />
                    </Form.Item>
                  </Col>
                </Row>

                <Form.Item>
                  <Button
                    type="primary"
                    icon={<SaveOutlined />}
                    htmlType="submit"
                    loading={loading}
                    className="save-button"
                    size="large"
                  >
                    保存配置
                  </Button>
                </Form.Item>
              </Form>
            </Card>
          </TabPane>

          <TabPane 
            tab={<span><UploadOutlined />B站账号管理</span>} 
            key="bilibili"
          >
            <BilibiliAccountManager />
          </TabPane>

          <TabPane 
            tab={<span><InfoCircleOutlined />使用说明</span>} 
            key="help"
          >
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
                
                <div className="instruction-item">
                  <Title level={5} className="instruction-title">
                    <InfoCircleOutlined /> 3. B站投稿功能
                  </Title>
                  <Paragraph className="instruction-text">
                    • 在"B站账号管理"标签页添加您的B站账号<br />
                    • 在项目详情页选择切片后点击"投稿到B站"按钮<br />
                    • 系统会自动处理投稿任务并跟踪状态
                  </Paragraph>
                </div>
                
                <div className="instruction-item">
                  <Title level={5} className="instruction-title">
                    <InfoCircleOutlined /> 4. 测试连接
                  </Title>
                  <Paragraph className="instruction-text">
                    保存前建议先测试API密钥是否有效，确保服务正常运行
                  </Paragraph>
                </div>
              </Space>
            </Card>
          </TabPane>
        </Tabs>
      </div>
    </Content>
  )
}

export default SettingsPage