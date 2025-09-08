import React, { useState } from 'react'
import { Modal, Steps, Card, Typography, Alert, Button, Space, Divider, Image } from 'antd'
import { QuestionCircleOutlined, CopyOutlined, CheckOutlined } from '@ant-design/icons'

const { Title, Paragraph, Text } = Typography
const { Step } = Steps

interface CookieHelperProps {
  visible: boolean
  onClose: () => void
}

const CookieHelper: React.FC<CookieHelperProps> = ({ visible, onClose }) => {
  const [currentStep, setCurrentStep] = useState(0)
  const [copied, setCopied] = useState(false)

  const steps = [
    {
      title: '登录B站',
      description: '在浏览器中登录B站账号',
      content: (
        <div>
          <Alert
            message="第一步：登录B站"
            description="请确保您已经在浏览器中成功登录了B站账号"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          <Card size="small">
            <Paragraph>
              1. 打开浏览器，访问 <Text code>https://www.bilibili.com</Text>
            </Paragraph>
            <Paragraph>
              2. 点击右上角的"登录"按钮
            </Paragraph>
            <Paragraph>
              3. 使用您的B站账号登录
            </Paragraph>
            <Paragraph>
              4. 确认登录成功后，您应该能看到您的用户名显示在右上角
            </Paragraph>
          </Card>
        </div>
      )
    },
    {
      title: '打开开发者工具',
      description: '按F12打开浏览器开发者工具',
      content: (
        <div>
          <Alert
            message="第二步：打开开发者工具"
            description="使用快捷键打开浏览器的开发者工具"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          <Card size="small">
            <Paragraph>
              <Text strong>Windows/Linux:</Text> 按 <Text code>F12</Text> 键
            </Paragraph>
            <Paragraph>
              <Text strong>Mac:</Text> 按 <Text code>Command + Option + I</Text>
            </Paragraph>
            <Paragraph>
              或者右键点击页面空白处，选择"检查"或"Inspect"
            </Paragraph>
            <Divider />
            <Paragraph type="secondary">
              开发者工具会在页面底部或右侧打开，包含多个标签页
            </Paragraph>
          </Card>
        </div>
      )
    },
    {
      title: '切换到Network标签',
      description: '找到Network（网络）标签页',
      content: (
        <div>
          <Alert
            message="第三步：切换到Network标签"
            description="在开发者工具中找到Network标签页"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          <Card size="small">
            <Paragraph>
              1. 在开发者工具顶部找到标签页
            </Paragraph>
            <Paragraph>
              2. 点击 <Text code>Network</Text> 标签
            </Paragraph>
            <Paragraph>
              3. 确保Network面板是空的（如果有内容，点击清除按钮）
            </Paragraph>
            <Divider />
            <Paragraph type="secondary">
              Network标签页用于监控网页的网络请求，包括Cookie信息
            </Paragraph>
          </Card>
        </div>
      )
    },
    {
      title: '刷新页面',
      description: '刷新B站页面以捕获请求',
      content: (
        <div>
          <Alert
            message="第四步：刷新页面"
            description="刷新B站页面以捕获网络请求"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          <Card size="small">
            <Paragraph>
              1. 确保Network标签页已打开
            </Paragraph>
            <Paragraph>
              2. 按 <Text code>F5</Text> 或点击浏览器的刷新按钮
            </Paragraph>
            <Paragraph>
              3. 观察Network面板中出现的请求列表
            </Paragraph>
            <Divider />
            <Paragraph type="secondary">
              刷新后，Network面板会显示页面加载过程中的所有网络请求
            </Paragraph>
          </Card>
        </div>
      )
    },
    {
      title: '找到Cookie',
      description: '在请求头中找到Cookie信息',
      content: (
        <div>
          <Alert
            message="第五步：找到Cookie信息"
            description="在任意请求中找到Cookie字段"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          <Card size="small">
            <Paragraph>
              1. 在Network面板中找到任意一个请求（通常选择第一个）
            </Paragraph>
            <Paragraph>
              2. 点击该请求，在右侧面板中找到 <Text code>Headers</Text> 标签
            </Paragraph>
            <Paragraph>
              3. 在 <Text code>Request Headers</Text> 部分找到 <Text code>Cookie</Text> 字段
            </Paragraph>
            <Paragraph>
              4. Cookie字段的值就是您需要的完整Cookie字符串
            </Paragraph>
            <Divider />
            <Paragraph type="secondary">
              Cookie字符串通常很长，包含多个键值对，用分号分隔
            </Paragraph>
          </Card>
        </div>
      )
    },
    {
      title: '复制Cookie',
      description: '复制完整的Cookie字符串',
      content: (
        <div>
          <Alert
            message="第六步：复制Cookie"
            description="复制完整的Cookie字符串到剪贴板"
            type="success"
            showIcon
            style={{ marginBottom: 16 }}
          />
          <Card size="small">
            <Paragraph>
              1. 右键点击Cookie字段的值
            </Paragraph>
            <Paragraph>
              2. 选择"复制值"或"Copy value"
            </Paragraph>
            <Paragraph>
              3. 或者双击选中整个Cookie值，然后按 <Text code>Ctrl+C</Text> 复制
            </Paragraph>
            <Divider />
            <Paragraph type="secondary">
              复制的Cookie字符串可以直接粘贴到AutoClip的Cookie输入框中
            </Paragraph>
            <Alert
              message="重要提示"
              description="Cookie包含您的登录信息，请妥善保管，不要分享给他人"
              type="warning"
              showIcon
            />
          </Card>
        </div>
      )
    }
  ]

  const handleCopy = () => {
    const cookieExample = "SESSDATA=your_sessdata_here; bili_jct=your_bili_jct_here; DedeUserID=your_dedeuserid_here"
    navigator.clipboard.writeText(cookieExample).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <Modal
      title={
        <Space>
          <QuestionCircleOutlined />
          <span>Cookie获取指南</span>
        </Space>
      }
      open={visible}
      onCancel={onClose}
      footer={[
        <Button key="back" onClick={onClose}>
          关闭
        </Button>,
        <Button
          key="copy"
          icon={copied ? <CheckOutlined /> : <CopyOutlined />}
          onClick={handleCopy}
        >
          {copied ? '已复制' : '复制示例'}
        </Button>
      ]}
      width={700}
    >
      <div style={{ marginBottom: 16 }}>
        <Alert
          message="Cookie导入是最安全的登录方式"
          description="相比扫码登录，Cookie导入不会触发B站的风控机制，是最推荐的登录方式。"
          type="success"
          showIcon
        />
      </div>

      <Steps current={currentStep} onChange={setCurrentStep} direction="vertical" size="small">
        {steps.map((step, index) => (
          <Step key={index} title={step.title} description={step.description} />
        ))}
      </Steps>

      <div style={{ marginTop: 24, padding: 16, backgroundColor: '#f5f5f5', borderRadius: 8 }}>
        {steps[currentStep].content}
      </div>

      <Divider />

      <Card size="small" title="Cookie格式示例">
        <Paragraph code style={{ fontSize: '12px', wordBreak: 'break-all' }}>
          SESSDATA=your_sessdata_here; bili_jct=your_bili_jct_here; DedeUserID=your_dedeuserid_here; buvid3=your_buvid3_here
        </Paragraph>
        <Paragraph type="secondary" style={{ fontSize: '12px' }}>
          注意：实际的Cookie值会比这个示例长很多，包含更多的字段
        </Paragraph>
      </Card>
    </Modal>
  )
}

export default CookieHelper

