import React from 'react'
import { Badge, Tooltip } from 'antd'
import { Project } from '../store/useProjectStore'
// import { 
//   getProjectStatusConfig, 
//   normalizeProjectStatus 
// } from '../utils/statusUtils'

interface ProjectStatusIndicatorProps {
  project: Project
  showProgress?: boolean
  size?: 'small' | 'default' | 'large'
}

const ProjectStatusIndicator: React.FC<ProjectStatusIndicatorProps> = ({
  project,
  size = 'default'
}) => {
  // 暂时使用简单的状态处理
  const normalizedStatus = project.status === 'error' ? 'failed' : project.status

  const getStepName = () => {
    if (normalizedStatus === 'processing' && project.current_step) {
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
    return '处理中'
  }

  const getStatusConfig = () => {
    switch (normalizedStatus) {
      case 'processing':
        return { text: '处理中', badgeStatus: 'processing' as const, color: '#1890ff' }
      case 'completed':
        return { text: '已完成', badgeStatus: 'success' as const, color: '#52c41a' }
      case 'failed':
        return { text: '失败', badgeStatus: 'error' as const, color: '#ff4d4f' }
      default:
        return { text: '未知', badgeStatus: 'default' as const, color: '#d9d9d9' }
    }
  }

  const config = getStatusConfig()

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
        {config.text}
      </span>
      <span>{config.text}</span>
    </div>
  )
}

export default ProjectStatusIndicator