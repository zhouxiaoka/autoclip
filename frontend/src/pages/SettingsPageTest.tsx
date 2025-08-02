import React from 'react'
import { Layout, Card, Form, Input, Button, Typography, Space, Alert, Divider, Row, Col } from 'antd'
import { KeyOutlined, SaveOutlined, ApiOutlined, SettingOutlined, InfoCircleOutlined } from '@ant-design/icons'
import './SettingsPage.css'

const { Content } = Layout
const { Title, Text, Paragraph } = Typography

const SettingsPageTest: React.FC = () => {
  const [form] = Form.useForm()

  return (
    <Content className="settings-page">
      <div className="settings-container">
        <Title level={2} className="settings-title">
          <SettingOutlined /> 系统配置测试
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

            <Form.Item className="form-item">
              <Button
                type="default"
                icon={<ApiOutlined />}
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
                  <Input placeholder="qwen-plus" className="settings-input" />
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

            <Form.Item className="form-item">
              <Button
                type="primary"
                htmlType="submit"
                icon={<SaveOutlined />}
                size="large"
                className="save-button"
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
            
            <div className="instruction-item">
              <Title level={5} className="instruction-title">
                <InfoCircleOutlined /> 3. 测试连接
              </Title>
              <Paragraph className="instruction-text">
                保存前建议先测试API密钥是否有效，确保服务正常运行
              </Paragraph>
            </div>
          </Space>
        </Card>
      </div>
    </Content>
  )
}

export default SettingsPageTest 