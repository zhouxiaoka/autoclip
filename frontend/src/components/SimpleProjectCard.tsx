/**
 * 简化的项目卡片组件 - 集成新的进度系统
 */

import React, { useState, useEffect } from 'react'
import { Card, Typography, Space, Button, Tag, Tooltip, Modal, message } from 'antd'
import { 
  PlayCircleOutlined, 
  EyeOutlined, 
  DeleteOutlined, 
  ReloadOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { SimpleProgressBar } from './SimpleProgressBar'
import { 
  useSimpleProgressStore, 
  getStageDisplayName, 
  getStageColor, 
  isCompleted, 
  isFailed,
  SimpleProgress 
} from '../stores/useSimpleProgressStore'

const { Title, Text } = Typography

interface Project {
  id: string
  title: string
  description?: string
  status: string
  created_at: string
  updated_at: string
  video_path?: string
  srt_path?: string
  category?: string
}

interface SimpleProjectCardProps {
  project: Project
  onStartProcessing?: (projectId: string) => void
  onViewDetails?: (projectId: string) => void
  onDelete?: (projectId: string) => void
  onRetry?: (projectId: string) => void
}

export const SimpleProjectCard: React.FC<SimpleProjectCardProps> = ({
  project,
  onStartProcessing,
  onViewDetails,
  onDelete,
  onRetry
}) => {
  const navigate = useNavigate()
  const { getProgress, startPolling, stopPolling } = useSimpleProgressStore()
  const [showProgress, setShowProgress] = useState(false)
  
  const progress = getProgress(project.id)

  // 根据项目状态决定是否显示进度
  useEffect(() => {
    if (project.status === 'processing') {
      setShowProgress(true)
      // 开始轮询这个项目的进度
      startPolling([project.id], 2000)
    } else {
      setShowProgress(false)
      stopPolling()
    }
  }, [project.status, project.id, startPolling, stopPolling])

  const handleStartProcessing = () => {
    if (onStartProcessing) {
      onStartProcessing(project.id)
    }
  }

  const handleViewDetails = () => {
    if (onViewDetails) {
      onViewDetails(project.id)
    } else {
      navigate(`/project/${project.id}`)
    }
  }

  const handleDelete = () => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除项目 "${project.title}" 吗？此操作不可撤销。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => {
        if (onDelete) {
          onDelete(project.id)
        }
      }
    })
  }

  const handleRetry = () => {
    if (onRetry) {
      onRetry(project.id)
    }
  }

  // 获取状态图标和颜色
  const getStatusConfig = (status: string, progress?: SimpleProgress) => {
    if (progress && isFailed(progress.message)) {
      return {
        icon: <ExclamationCircleOutlined />,
        color: '#ff4d4f',
        text: '处理失败'
      }
    }
    
    if (progress && isCompleted(progress.stage)) {
      return {
        icon: <CheckCircleOutlined />,
        color: '#52c41a',
        text: '处理完成'
      }
    }
    
    if (status === 'processing' || (progress && !isCompleted(progress.stage))) {
      return {
        icon: <ReloadOutlined spin />,
        color: '#1890ff',
        text: '处理中'
      }
    }
    
    return {
      icon: <PlayCircleOutlined />,
      color: '#666666',
      text: '等待处理'
    }
  }

  const statusConfig = getStatusConfig(project.status, progress)
  const canStart = project.status === 'pending' || project.status === 'failed'
  const canRetry = project.status === 'failed' || (progress && isFailed(progress.message))

  return (
    <Card
      hoverable
      style={{ margin: '8px 0' }}
      actions={[
        canStart && (
          <Tooltip title="开始处理">
            <Button 
              type="primary" 
              icon={<PlayCircleOutlined />}
              onClick={handleStartProcessing}
            >
              开始处理
            </Button>
          </Tooltip>
        ),
        canRetry && (
          <Tooltip title="重试">
            <Button 
              icon={<ReloadOutlined />}
              onClick={handleRetry}
            >
              重试
            </Button>
          </Tooltip>
        ),
        <Tooltip title="查看详情">
          <Button 
            icon={<EyeOutlined />}
            onClick={handleViewDetails}
          >
            查看详情
          </Button>
        </Tooltip>,
        <Tooltip title="删除项目">
          <Button 
            danger 
            icon={<DeleteOutlined />}
            onClick={handleDelete}
          >
            删除
          </Button>
        </Tooltip>
      ].filter(Boolean)}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        {/* 项目标题和状态 */}
        <Space align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
          <Title level={5} style={{ margin: 0, flex: 1 }}>
            {project.title}
          </Title>
          <Tag 
            color={statusConfig.color} 
            icon={statusConfig.icon}
            style={{ margin: 0 }}
          >
            {statusConfig.text}
          </Tag>
        </Space>

        {/* 项目描述 */}
        {project.description && (
          <Text type="secondary" style={{ fontSize: '12px' }}>
            {project.description}
          </Text>
        )}

        {/* 分类标签 */}
        {project.category && (
          <Tag color="blue" style={{ fontSize: '11px' }}>
            {project.category}
          </Tag>
        )}

        {/* 进度条 */}
        {showProgress && (
          <SimpleProgressBar
            projectId={project.id}
            autoStart={false} // 已经在useEffect中处理
            showDetails={true}
            onProgressUpdate={(progress) => {
              // 如果处理完成，更新显示状态
              if (isCompleted(progress.stage)) {
                setShowProgress(false)
                message.success('项目处理完成！')
              } else if (isFailed(progress.message)) {
                message.error('项目处理失败！')
              }
            }}
          />
        )}

        {/* 时间信息 */}
        <Space style={{ fontSize: '11px', color: '#999' }}>
          <Text type="secondary">
            创建: {new Date(project.created_at).toLocaleDateString()}
          </Text>
          <Text type="secondary">
            更新: {new Date(project.updated_at).toLocaleDateString()}
          </Text>
        </Space>
      </Space>
    </Card>
  )
}
