/**
 * 进度系统测试页面
 */

import React, { useState } from 'react'
import { Card, Button, Space, Typography, Row, Col, Input, Select, message } from 'antd'
import { PlayCircleOutlined, StopOutlined, ReloadOutlined } from '@ant-design/icons'
import { UnifiedStatusBar, SimpleProgressDisplay } from '../components/UnifiedStatusBar'
import { useSimpleProgressStore } from '../stores/useSimpleProgressStore'

const { Title, Text } = Typography
const { Option } = Select

export const ProgressTestPage: React.FC = () => {
  const { startPolling, stopPolling, isPolling, clearAllProgress } = useSimpleProgressStore()
  const [testProjectId, setTestProjectId] = useState('test-project-1')
  const [testStatus, setTestStatus] = useState('pending')
  const [downloadProgress, setDownloadProgress] = useState(0)

  // 模拟开始下载
  const handleStartDownload = () => {
    setTestStatus('downloading')
    setDownloadProgress(0)
    
    // 模拟下载进度
    const interval = setInterval(() => {
      setDownloadProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval)
          setTimeout(() => {
            setTestStatus('processing')
            message.success('下载完成，开始处理')
          }, 1000)
          return 100
        }
        return prev + Math.random() * 20
      })
    }, 500)
  }

  // 模拟开始处理
  const handleStartProcessing = () => {
    setTestStatus('processing')
    startPolling([testProjectId], 2000)
    message.info('开始处理，请查看后端日志')
  }

  // 模拟完成
  const handleComplete = () => {
    setTestStatus('completed')
    stopPolling()
    message.success('处理完成')
  }

  // 模拟失败
  const handleFail = () => {
    setTestStatus('failed')
    stopPolling()
    message.error('处理失败')
  }

  // 重置
  const handleReset = () => {
    setTestStatus('pending')
    setDownloadProgress(0)
    stopPolling()
    clearAllProgress()
    message.info('已重置')
  }

  return (
    <div style={{ padding: '24px', maxWidth: '800px', margin: '0 auto' }}>
      <Title level={2}>进度系统测试</Title>
      
      <Card title="测试控制面板" style={{ marginBottom: '24px' }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Row gutter={16}>
            <Col span={12}>
              <Text strong>项目ID:</Text>
              <Input
                value={testProjectId}
                onChange={(e) => setTestProjectId(e.target.value)}
                placeholder="输入项目ID"
                style={{ marginTop: '8px' }}
              />
            </Col>
            <Col span={12}>
              <Text strong>当前状态:</Text>
              <Select
                value={testStatus}
                onChange={setTestStatus}
                style={{ width: '100%', marginTop: '8px' }}
              >
                <Option value="pending">等待中</Option>
                <Option value="downloading">下载中</Option>
                <Option value="processing">处理中</Option>
                <Option value="completed">已完成</Option>
                <Option value="failed">失败</Option>
              </Select>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Text strong>下载进度:</Text>
              <Input
                type="number"
                value={downloadProgress}
                onChange={(e) => setDownloadProgress(Number(e.target.value))}
                min={0}
                max={100}
                style={{ marginTop: '8px' }}
              />
            </Col>
            <Col span={12}>
              <Text strong>轮询状态:</Text>
              <div style={{ marginTop: '8px' }}>
                <Text type={isPolling ? 'success' : 'secondary'}>
                  {isPolling ? '正在轮询' : '未轮询'}
                </Text>
              </div>
            </Col>
          </Row>

          <Space wrap>
            <Button 
              type="primary" 
              icon={<PlayCircleOutlined />}
              onClick={handleStartDownload}
              disabled={testStatus !== 'pending'}
            >
              开始下载
            </Button>
            <Button 
              icon={<PlayCircleOutlined />}
              onClick={handleStartProcessing}
              disabled={testStatus !== 'downloading' && testStatus !== 'pending'}
            >
              开始处理
            </Button>
            <Button 
              type="primary"
              onClick={handleComplete}
              disabled={testStatus !== 'processing'}
            >
              完成
            </Button>
            <Button 
              danger
              onClick={handleFail}
              disabled={testStatus !== 'processing'}
            >
              失败
            </Button>
            <Button 
              icon={<ReloadOutlined />}
              onClick={handleReset}
            >
              重置
            </Button>
          </Space>
        </Space>
      </Card>

      <Card title="状态显示测试">
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text strong>统一状态栏:</Text>
          <UnifiedStatusBar
            projectId={testProjectId}
            status={testStatus}
            downloadProgress={downloadProgress}
            onStatusChange={(newStatus) => {
              console.log('状态变化:', newStatus)
            }}
            onDownloadProgressUpdate={(progress) => {
              console.log('下载进度更新:', progress)
            }}
          />

          <Text strong>详细进度显示:</Text>
          <SimpleProgressDisplay
            projectId={testProjectId}
            status={testStatus}
            showDetails={true}
          />

          <Text strong>说明:</Text>
          <ul style={{ fontSize: '12px', color: '#666' }}>
            <li>点击"开始下载"模拟下载过程，进度会自动增长</li>
            <li>下载完成后会自动切换到"处理中"状态</li>
            <li>处理中状态会轮询后端API获取进度</li>
            <li>可以手动点击"完成"或"失败"来测试终态</li>
            <li>点击"重置"清除所有状态</li>
          </ul>
        </Space>
      </Card>
    </div>
  )
}
