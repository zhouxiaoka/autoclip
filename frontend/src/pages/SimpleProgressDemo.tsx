/**
 * 简化进度系统演示页面
 */

import React, { useState, useEffect } from 'react'
import { 
  Card, 
  Typography, 
  Space, 
  Button, 
  Row, 
  Col, 
  Divider, 
  message,
  Input,
  Select
} from 'antd'
import { 
  PlayCircleOutlined, 
  StopOutlined, 
  ReloadOutlined,
  PlusOutlined
} from '@ant-design/icons'
import { SimpleProgressBar, BatchProgressBar } from '../components/SimpleProgressBar'
import { SimpleProjectCard } from '../components/SimpleProjectCard'
import { useSimpleProgressStore } from '../stores/useSimpleProgressStore'

const { Title, Text, Paragraph } = Typography
const { Option } = Select

// 模拟项目数据
const mockProjects = [
  {
    id: 'demo-project-1',
    title: 'AI技术解析视频',
    description: '深度解析人工智能技术发展历程',
    status: 'pending',
    created_at: '2024-01-15T10:00:00Z',
    updated_at: '2024-01-15T10:00:00Z',
    category: 'knowledge'
  },
  {
    id: 'demo-project-2', 
    title: '创业经验分享',
    description: '分享创业路上的酸甜苦辣',
    status: 'processing',
    created_at: '2024-01-14T15:30:00Z',
    updated_at: '2024-01-15T09:45:00Z',
    category: 'business'
  },
  {
    id: 'demo-project-3',
    title: '游戏评测视频',
    description: '最新游戏深度评测',
    status: 'completed',
    created_at: '2024-01-13T20:15:00Z',
    updated_at: '2024-01-14T16:20:00Z',
    category: 'entertainment'
  }
]

export const SimpleProgressDemo: React.FC = () => {
  const { 
    startPolling, 
    stopPolling, 
    isPolling, 
    getAllProgress,
    clearAllProgress 
  } = useSimpleProgressStore()

  const [projects, setProjects] = useState(mockProjects)
  const [selectedProjectIds, setSelectedProjectIds] = useState<string[]>([])
  const [pollingInterval, setPollingInterval] = useState(2000)
  const [newProjectId, setNewProjectId] = useState('')

  // 模拟开始处理项目
  const handleStartProcessing = (projectId: string) => {
    setProjects(prev => prev.map(p => 
      p.id === projectId ? { ...p, status: 'processing' } : p
    ))
    message.success(`开始处理项目: ${projectId}`)
  }

  // 模拟查看详情
  const handleViewDetails = (projectId: string) => {
    message.info(`查看项目详情: ${projectId}`)
  }

  // 模拟删除项目
  const handleDelete = (projectId: string) => {
    setProjects(prev => prev.filter(p => p.id !== projectId))
    message.success(`删除项目: ${projectId}`)
  }

  // 模拟重试项目
  const handleRetry = (projectId: string) => {
    setProjects(prev => prev.map(p => 
      p.id === projectId ? { ...p, status: 'processing' } : p
    ))
    message.success(`重试项目: ${projectId}`)
  }

  // 添加新项目
  const handleAddProject = () => {
    if (!newProjectId.trim()) {
      message.warning('请输入项目ID')
      return
    }

    const newProject = {
      id: newProjectId,
      title: `新项目 ${newProjectId}`,
      description: '这是一个新添加的演示项目',
      status: 'pending' as const,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      category: 'default'
    }

    setProjects(prev => [...prev, newProject])
    setNewProjectId('')
    message.success(`添加项目: ${newProjectId}`)
  }

  // 开始轮询选中的项目
  const handleStartPolling = () => {
    if (selectedProjectIds.length === 0) {
      message.warning('请选择要轮询的项目')
      return
    }
    startPolling(selectedProjectIds, pollingInterval)
    message.success(`开始轮询 ${selectedProjectIds.length} 个项目`)
  }

  // 停止轮询
  const handleStopPolling = () => {
    stopPolling()
    message.info('停止轮询')
  }

  // 清除所有进度
  const handleClearProgress = () => {
    clearAllProgress()
    message.success('清除所有进度数据')
  }

  const allProgress = getAllProgress()

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Title level={2}>简化进度系统演示</Title>
      
      <Paragraph>
        这是一个基于固定阶段和轮询的简化进度系统演示。
        系统使用6个固定阶段，每个阶段有固定的权重，通过轮询API获取最新进度。
      </Paragraph>

      <Divider />

      {/* 控制面板 */}
      <Card title="控制面板" style={{ marginBottom: '24px' }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Row gutter={16}>
            <Col span={8}>
              <Text strong>轮询间隔:</Text>
              <Select
                value={pollingInterval}
                onChange={setPollingInterval}
                style={{ width: '100%', marginTop: '8px' }}
              >
                <Option value={1000}>1秒</Option>
                <Option value={2000}>2秒</Option>
                <Option value={3000}>3秒</Option>
                <Option value={5000}>5秒</Option>
              </Select>
            </Col>
            <Col span={8}>
              <Text strong>轮询状态:</Text>
              <div style={{ marginTop: '8px' }}>
                <Tag color={isPolling ? 'green' : 'red'}>
                  {isPolling ? '正在轮询' : '未轮询'}
                </Tag>
              </div>
            </Col>
            <Col span={8}>
              <Text strong>进度数据:</Text>
              <div style={{ marginTop: '8px' }}>
                <Tag color="blue">
                  {Object.keys(allProgress).length} 个项目
                </Tag>
              </div>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Space>
                <Button 
                  type="primary" 
                  icon={<PlayCircleOutlined />}
                  onClick={handleStartPolling}
                  disabled={isPolling}
                >
                  开始轮询
                </Button>
                <Button 
                  icon={<StopOutlined />}
                  onClick={handleStopPolling}
                  disabled={!isPolling}
                >
                  停止轮询
                </Button>
                <Button 
                  icon={<ReloadOutlined />}
                  onClick={handleClearProgress}
                >
                  清除进度
                </Button>
              </Space>
            </Col>
            <Col span={12}>
              <Space>
                <Input
                  placeholder="输入新项目ID"
                  value={newProjectId}
                  onChange={(e) => setNewProjectId(e.target.value)}
                  onPressEnter={handleAddProject}
                />
                <Button 
                  type="dashed" 
                  icon={<PlusOutlined />}
                  onClick={handleAddProject}
                >
                  添加项目
                </Button>
              </Space>
            </Col>
          </Row>

          <Row>
            <Col span={24}>
              <Text strong>选择要轮询的项目:</Text>
              <div style={{ marginTop: '8px' }}>
                <Select
                  mode="multiple"
                  placeholder="选择项目"
                  value={selectedProjectIds}
                  onChange={setSelectedProjectIds}
                  style={{ width: '100%' }}
                >
                  {projects.map(project => (
                    <Option key={project.id} value={project.id}>
                      {project.title} ({project.status})
                    </Option>
                  ))}
                </Select>
              </div>
            </Col>
          </Row>
        </Space>
      </Card>

      {/* 批量进度显示 */}
      {selectedProjectIds.length > 0 && (
        <Card title="批量进度显示" style={{ marginBottom: '24px' }}>
          <BatchProgressBar
            projectIds={selectedProjectIds}
            autoStart={false}
            pollingInterval={pollingInterval}
            showDetails={true}
            onProgressUpdate={(projectId, progress) => {
              console.log(`项目 ${projectId} 进度更新:`, progress)
            }}
          />
        </Card>
      )}

      {/* 项目卡片列表 */}
      <Card title="项目列表">
        <Row gutter={[16, 16]}>
          {projects.map(project => (
            <Col span={24} key={project.id}>
              <SimpleProjectCard
                project={project}
                onStartProcessing={handleStartProcessing}
                onViewDetails={handleViewDetails}
                onDelete={handleDelete}
                onRetry={handleRetry}
              />
            </Col>
          ))}
        </Row>
      </Card>

      {/* 当前进度数据 */}
      {Object.keys(allProgress).length > 0 && (
        <Card title="当前进度数据" style={{ marginTop: '24px' }}>
          <pre style={{ 
            background: '#f5f5f5', 
            padding: '12px', 
            borderRadius: '4px',
            fontSize: '12px',
            maxHeight: '300px',
            overflow: 'auto'
          }}>
            {JSON.stringify(allProgress, null, 2)}
          </pre>
        </Card>
      )}
    </div>
  )
}
