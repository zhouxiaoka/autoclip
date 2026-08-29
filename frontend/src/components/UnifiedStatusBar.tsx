/**
 * 统一状态栏组件 - 替换旧的复杂进度系统
 * 支持下载中、处理中、完成等状态的统一显示
 */

import React, { useEffect, useState } from 'react'
import { Progress, Typography } from 'antd'
import { useSimpleProgressStore, getStageDisplayName, getStageColor, isCompleted, isFailed } from '../stores/useSimpleProgressStore'

const { Text } = Typography

interface UnifiedStatusBarProps {
  projectId: string
  status: string
  downloadProgress?: number
  onStatusChange?: (status: string) => void
  onDownloadProgressUpdate?: (progress: number) => void
}

export const UnifiedStatusBar: React.FC<UnifiedStatusBarProps> = ({
  projectId,
  status,
  downloadProgress = 0,
  onStatusChange,
  onDownloadProgressUpdate
}) => {
  const { getProgress, startPolling, stopPolling } = useSimpleProgressStore()
  const [isPolling, setIsPolling] = useState(false)
  const [currentDownloadProgress, setCurrentDownloadProgress] = useState(downloadProgress)
  
  const progress = getProgress(projectId)

  // 根据状态决定是否轮询
  useEffect(() => {
    // 如果已有进度且已到达终态，则不启动轮询
    if (progress && (isCompleted(progress.stage) || isFailed(progress.message))) {
      if (isPolling) {
        console.log(`进度已终态，停止轮询: ${projectId}`)
        stopPolling()
        setIsPolling(false)
      }
      return
    }

    if ((status === 'processing' || status === 'pending') && !isPolling) {
      console.log(`开始轮询处理进度: ${projectId}`)
      startPolling([projectId], 5000) // 5秒轮询一次，减少频繁请求
      setIsPolling(true)
    } else if (status !== 'processing' && status !== 'pending' && isPolling) {
      console.log(`停止轮询处理进度: ${projectId}`)
      stopPolling()
      setIsPolling(false)
    }

    return () => {
      if (isPolling) {
        console.log(`清理轮询: ${projectId}`)
        stopPolling()
        setIsPolling(false)
      }
    }
  }, [status, projectId, isPolling, startPolling, stopPolling, progress])

  // 下载进度轮询
  useEffect(() => {
    if (status === 'downloading') {
      const pollDownloadProgress = async () => {
        try {
          console.log(`轮询下载进度: ${projectId}`)
          const response = await fetch(`/api/v1/projects/${projectId}`)
          if (response.ok) {
            const projectData = await response.json()
            console.log('项目数据:', projectData)
            const newProgress = projectData.processing_config?.download_progress
              || projectData.settings?.download_progress
              || 0
            console.log(`下载进度更新: ${newProgress}%`)
            setCurrentDownloadProgress(newProgress)
            onDownloadProgressUpdate?.(newProgress)
            
            // 如果下载完成，检查是否需要切换到处理状态
            if (newProgress >= 100) {
              console.log('下载完成，切换到处理状态')
              setTimeout(() => {
                onStatusChange?.('processing')
              }, 1000)
            }
          } else {
            console.error('获取项目数据失败:', response.status, response.statusText)
          }
        } catch (error) {
          console.error('获取下载进度失败:', error)
        }
      }

      // 立即获取一次
      pollDownloadProgress()
      
      // 每5秒轮询一次，减少频繁请求
      const interval = setInterval(pollDownloadProgress, 5000)
      
      return () => clearInterval(interval)
    }
  }, [status, projectId, onDownloadProgressUpdate, onStatusChange])

  // 处理状态变化
  useEffect(() => {
    if (progress) {
      // 进度到达终态时，立刻停止轮询并同步状态
      if (isCompleted(progress.stage) || isFailed(progress.message)) {
        if (isPolling) {
          console.log(`进度达到终态，停止轮询: ${projectId}`)
          stopPolling()
          setIsPolling(false)
        }
        if (onStatusChange) {
          onStatusChange(isCompleted(progress.stage) ? 'completed' : 'failed')
        }
      }
    }
  }, [progress, onStatusChange])

  // ===== Calm Premium 状态展示（见 DESIGN.md）=====
  // 进行中：细进度线 + 标签 + 右侧 mono 百分比
  const ProgressRow = ({ label, percent }: { label: string; percent: number }) => (
    <div style={{ width: '100%' }}>
      <div style={{ height: 4, background: 'var(--ac-line)', borderRadius: 999, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${Math.max(0, Math.min(100, percent))}%`, background: 'var(--ac-accent)', borderRadius: 999, transition: 'width .4s ease' }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 9 }}>
        <span style={{ color: 'var(--ac-sub)', fontSize: 12.5 }}>{label}</span>
        <span className="ac-mono" style={{ color: 'var(--ac-accent)', fontSize: 12.5 }}>{Math.round(percent)}%</span>
      </div>
    </div>
  )
  // 终态：小圆点 + 标签
  const StatusRow = ({ label, dot, color }: { label: string; dot: string; color: string }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, height: 4 + 9 + 12.5 + 2, minHeight: 26 }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: dot, flex: '0 0 auto' }} />
      <span style={{ color, fontSize: 12.5 }}>{label}</span>
    </div>
  )

  if (status === 'importing') return <ProgressRow label="Importing" percent={downloadProgress} />
  if (status === 'downloading') return <ProgressRow label="Downloading" percent={currentDownloadProgress} />

  if (status === 'processing') {
    if (!progress) return <ProgressRow label="Starting" percent={0} />
    const { stage, percent, message } = progress
    if (isFailed(message)) return <StatusRow label="Failed" dot="var(--ac-error)" color="var(--ac-error)" />
    return <ProgressRow label={getStageDisplayName(stage)} percent={percent} />
  }

  if (status === 'completed') return <StatusRow label="Completed" dot="var(--ac-ok)" color="var(--ac-sub)" />
  if (status === 'failed') return <StatusRow label="Failed" dot="var(--ac-error)" color="var(--ac-error)" />

  // Waiting
  return <StatusRow label="Waiting" dot="var(--ac-muted)" color="var(--ac-muted)" />
}

// 简化的进度条组件 - 用于详细进度显示
interface SimpleProgressDisplayProps {
  projectId: string
  status: string
  showDetails?: boolean
}

export const SimpleProgressDisplay: React.FC<SimpleProgressDisplayProps> = ({
  projectId,
  status,
  showDetails = false
}) => {
  const { getProgress } = useSimpleProgressStore()
  const progress = getProgress(projectId)

  if (status !== 'processing' || !progress || !showDetails) {
    return null
  }

  const { stage, percent, message } = progress
  const stageColor = getStageColor(stage)

  return (
    <div style={{ marginTop: '8px' }}>
      <Progress
        percent={percent}
        strokeColor={stageColor}
        showInfo={true}
        size="small"
        format={(percent) => `${percent}%`}
      />
      {message && (
        <Text type="secondary" style={{ fontSize: '11px', display: 'block', marginTop: '4px' }}>
          {message}
        </Text>
      )}
    </div>
  )
}
