/**
 * 简化的进度条组件 - 基于固定阶段
 */

import React, { useEffect } from 'react'
import { Progress, Card, Typography, Space, Tag } from 'antd'
import { 
  useSimpleProgressStore, 
  getStageDisplayName, 
  getStageColor, 
  isCompleted, 
  isFailed,
  SimpleProgress 
} from '../stores/useSimpleProgressStore'

const { Text } = Typography

interface SimpleProgressBarProps {
  projectId: string
  autoStart?: boolean
  pollingInterval?: number
  showDetails?: boolean
  onProgressUpdate?: (progress: SimpleProgress) => void
}

export const SimpleProgressBar: React.FC<SimpleProgressBarProps> = ({
  projectId,
  autoStart = true,
  pollingInterval = 2000,
  showDetails = true,
  onProgressUpdate
}) => {
  const { 
    getProgress, 
    startPolling, 
    stopPolling, 
    isPolling 
  } = useSimpleProgressStore()

  const progress = getProgress(projectId)

  // 自动开始轮询
  useEffect(() => {
    if (autoStart && projectId) {
      startPolling([projectId], pollingInterval)
      
      return () => {
        stopPolling()
      }
    }
  }, [projectId, autoStart, pollingInterval, startPolling, stopPolling])

  // 通知父组件进度更新
  useEffect(() => {
    if (progress && onProgressUpdate) {
      onProgressUpdate(progress)
    }
  }, [progress, onProgressUpdate])

  // 如果没有进度数据，显示等待状态
  if (!progress) {
    return (
      <Card size="small" style={{ margin: '8px 0' }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text type="secondary">等待开始处理...</Text>
          <Progress 
            percent={0} 
            status="active" 
            strokeColor="#1890ff"
            showInfo={false}
          />
        </Space>
      </Card>
    )
  }

  const { stage, percent, message, ts } = progress
  const stageDisplayName = getStageDisplayName(stage)
  const stageColor = getStageColor(stage)
  const completed = isCompleted(stage)
  const failed = isFailed(message)

  // 确定进度条状态
  let progressStatus: 'normal' | 'active' | 'success' | 'exception' = 'normal'
  if (failed) {
    progressStatus = 'exception'
  } else if (completed) {
    progressStatus = 'success'
  } else if (percent > 0) {
    progressStatus = 'active'
  }

  return (
    <Card size="small" style={{ margin: '8px 0' }}>
      <Space direction="vertical" style={{ width: '100%' }}>
        {/* 阶段标签和进度 */}
        <Space align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
          <Tag color={stageColor} style={{ margin: 0 }}>
            {stageDisplayName}
          </Tag>
          <Text strong style={{ color: stageColor }}>
            {percent}%
          </Text>
        </Space>

        {/* 进度条 */}
        <Progress
          percent={percent}
          status={progressStatus}
          strokeColor={stageColor}
          showInfo={false}
          size="small"
        />

        {/* 详细信息 */}
        {showDetails && message && (
          <Text type="secondary" style={{ fontSize: '12px' }}>
            {message}
          </Text>
        )}

        {/* 时间戳 */}
        {showDetails && ts > 0 && (
          <Text type="secondary" style={{ fontSize: '11px' }}>
            更新时间: {new Date(ts * 1000).toLocaleTimeString()}
          </Text>
        )}
      </Space>
    </Card>
  )
}

// 批量进度显示组件
interface BatchProgressBarProps {
  projectIds: string[]
  autoStart?: boolean
  pollingInterval?: number
  showDetails?: boolean
  onProgressUpdate?: (projectId: string, progress: SimpleProgress) => void
}

export const BatchProgressBar: React.FC<BatchProgressBarProps> = ({
  projectIds,
  autoStart = true,
  pollingInterval = 2000,
  showDetails = true,
  onProgressUpdate
}) => {
  const { 
    getAllProgress, 
    startPolling, 
    stopPolling, 
    isPolling 
  } = useSimpleProgressStore()

  const allProgress = getAllProgress()

  // 自动开始轮询
  useEffect(() => {
    if (autoStart && projectIds.length > 0) {
      startPolling(projectIds, pollingInterval)
      
      return () => {
        stopPolling()
      }
    }
  }, [projectIds, autoStart, pollingInterval, startPolling, stopPolling])

  // 通知父组件进度更新
  useEffect(() => {
    if (onProgressUpdate) {
      projectIds.forEach(projectId => {
        const progress = allProgress[projectId]
        if (progress) {
          onProgressUpdate(projectId, progress)
        }
      })
    }
  }, [allProgress, projectIds, onProgressUpdate])

  return (
    <div>
      {projectIds.map(projectId => (
        <SimpleProgressBar
          key={projectId}
          projectId={projectId}
          autoStart={false} // 批量模式下不自动开始
          showDetails={showDetails}
          onProgressUpdate={(progress) => onProgressUpdate?.(projectId, progress)}
        />
      ))}
    </div>
  )
}
