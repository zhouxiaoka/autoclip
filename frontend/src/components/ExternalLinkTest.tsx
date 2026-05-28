import React from 'react'
import { Button, Space, Typography } from 'antd'
import { LinkOutlined } from '@ant-design/icons'
import { openExternalLink } from '../utils/externalLinks'

const { Title, Text } = Typography

/**
 * 外部链接测试组件
 * 用于测试Tauri环境中的外部链接功能
 */
const ExternalLinkTest: React.FC = () => {
  const testLinks = [
    {
      name: 'DashScope (阿里云百炼)',
      url: 'https://dashscope.aliyun.com',
      description: '阿里云百炼平台，获取API Key'
    },
    {
      name: 'OpenAI',
      url: 'https://platform.openai.com/api-keys',
      description: 'OpenAI平台，获取API Key'
    },
    {
      name: 'Google AI Studio',
      url: 'https://aistudio.google.com/app/apikey',
      description: 'Google AI Studio，获取API Key'
    },
    {
      name: 'SiliconFlow',
      url: 'https://cloud.siliconflow.cn/',
      description: 'SiliconFlow平台，获取API Key'
    }
  ]

  const handleTestLink = async (url: string, name: string) => {
    try {
      await openExternalLink(url)
      console.log(`✅ 成功打开链接: ${name}`)
    } catch (error) {
      console.error(`❌ 打开链接失败: ${name}`, error)
    }
  }

  return (
    <div style={{ padding: '20px', maxWidth: '600px' }}>
      <Title level={3}>
        <LinkOutlined /> 外部链接测试
      </Title>
      
      <Text type="secondary">
        测试在Tauri环境中打开外部链接的功能。点击下面的按钮应该会在默认浏览器中打开对应的链接。
      </Text>

      <div style={{ marginTop: '20px' }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {testLinks.map((link, index) => (
            <div key={index} style={{ 
              border: '1px solid #d9d9d9', 
              borderRadius: '6px', 
              padding: '12px',
              backgroundColor: '#fafafa'
            }}>
              <div style={{ marginBottom: '8px' }}>
                <Text strong>{link.name}</Text>
              </div>
              <div style={{ marginBottom: '8px' }}>
                <Text type="secondary" style={{ fontSize: '12px' }}>
                  {link.description}
                </Text>
              </div>
              <div>
                <Text code style={{ fontSize: '12px', wordBreak: 'break-all' }}>
                  {link.url}
                </Text>
              </div>
              <div style={{ marginTop: '8px' }}>
                <Button 
                  type="primary" 
                  size="small"
                  onClick={() => handleTestLink(link.url, link.name)}
                >
                  测试打开链接
                </Button>
              </div>
            </div>
          ))}
        </Space>
      </div>

      <div style={{ marginTop: '20px', padding: '12px', backgroundColor: '#e6f7ff', borderRadius: '6px' }}>
        <Text type="secondary" style={{ fontSize: '12px' }}>
          💡 提示：如果链接无法打开，请检查：
          <br />
          1. 网络连接是否正常
          <br />
          2. 默认浏览器是否已设置
          <br />
          3. 系统是否允许应用打开外部链接
        </Text>
      </div>
    </div>
  )
}

export default ExternalLinkTest
