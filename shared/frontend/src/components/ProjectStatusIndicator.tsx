import React from 'react'
import { Badge, Progress, Tooltip, Typography } from 'antd'
import { 
  LoadingOutlined, 
  CheckCircleOutlined, 
  ExclamationCircleOutlined,
  ClockCircleOutlined,
  StopOutlined,
  QuestionCircleOutlined
} from '@ant-design/icons'
import { Project } from '../store/useProjectStore'

const { Text } = Typography

interface ProjectStatusIndicatorProps {
  project: Project
  showProgress?: boolean
  size?: 'small' | 'default' | 'large'
}

const ProjectStatusIndicator: React.FC<ProjectStatusIndicatorProps> = ({
  project,
  showProgress = true,
  size = 'default'
}) => {
  const getStatusConfig = () => {
    switch (project.status) {
      case 'pending':
        return {
          color: '#1890ff',
          icon: <ClockCircleOutlined />,
          text: '等待中',
          badgeStatus: 'processing' as const
        }
      case 'processing':
        return {
          color: '#52c41a',
          icon: <LoadingOutlined spin />,
          text: `处理中 (${project.current_step || 0}/${project.total_steps || 6})`,
          badgeStatus: 'processing' as const
        }
      case 'completed':
        return {
          color: '#52c41a',
          icon: <CheckCircleOutlined />,
          text: '已完成',
          badgeStatus: 'success' as const
        }
      case 'failed':
        return {
          color: '#ff4d4f',
          icon: <ExclamationCircleOutlined />,
          text: '处理失败',
          badgeStatus: 'error' as const
        }
      default:
        return {
          color: '#d9d9d9',
          icon: <QuestionCircleOutlined />,
          text: '未知状态',
          badgeStatus: 'default' as const
        }
    }
  }

  const config = getStatusConfig()
  const progress = project.status === 'processing' 
    ? ((project.current_step || 0) / (project.total_steps || 6)) * 100
    : project.status === 'completed' ? 100 : 0

  const getStepName = () => {
    if (project.status === 'processing' && project.current_step) {
      const stepNames = {
        1: '内容大纲分析',
        2: '时间轴生成',
        3: '片段评分',
        4: '标题生成',
        5: '主题聚类',
        6: '视频生成'
      }
      return stepNames[project.current_step as keyof typeof stepNames] || '处理中'
    }
    return config.text
  }

  if (size === 'small') {
    return (
      <Tooltip title={getStepName()}>
        <Badge status={config.badgeStatus} text={config.text} />
      </Tooltip>
    )
  }

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: '100%',
      padding: '4px 8px',
      borderRadius: '4px',
      backgroundColor: `${config.color}15`,
      border: `1px solid ${config.color}30`,
      color: config.color,
      fontSize: '12px',
      fontWeight: 500,
      minHeight: '24px'
    }}>
      <span style={{ marginRight: '4px', display: 'flex', alignItems: 'center' }}>
        {config.icon}
      </span>
      <span>{config.text}</span>
    </div>
  )
}

export default ProjectStatusIndicator