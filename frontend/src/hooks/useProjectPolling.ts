import { useEffect, useRef, useState } from 'react'
import { projectApi } from '../services/api'
import { Project, useProjectStore } from '../store/useProjectStore'

interface UseProjectPollingOptions {
  interval?: number // 轮询间隔，默认10秒
  onProjectsUpdate?: (projects: Project[]) => void
  enabled?: boolean // 是否启用轮询
}

export const useProjectPolling = ({
  interval = 30000, // 默认30秒，减少频繁请求
  onProjectsUpdate,
  enabled = true
}: UseProjectPollingOptions = {}) => {
  const [isPolling, setIsPolling] = useState(false)
  const intervalRef = useRef<number | null>(null)
  const [lastUpdateTime, setLastUpdateTime] = useState<number>(Date.now())

    const startPolling = () => {
    if (!enabled || intervalRef.current) return

    setIsPolling(true)
    
    const poll = async () => {
      try {
        // 实时获取isDragging状态
        const currentIsDragging = useProjectStore.getState().isDragging
        
        // 如果正在拖拽，跳过这次轮询
        if (currentIsDragging) {
          console.log('Skipping poll: dragging in progress')
          return
        }
        
        console.log('Polling projects...')
        const projects = await projectApi.getProjects()
        console.log('Polled projects:', projects)
        
        // 确保projects是数组类型
        const safeProjects = Array.isArray(projects) ? projects : []
        const hasProcessingProjects = safeProjects.some(p => p.status === 'processing')
        
        if (onProjectsUpdate) {
          console.log('Calling onProjectsUpdate with:', safeProjects)
          onProjectsUpdate(safeProjects)
        }
        
        setLastUpdateTime(Date.now())
        
        // 智能轮询：如果没有正在处理的项目，增加轮询间隔
        if (!hasProcessingProjects) {
          // 如果没有活跃项目，可以进一步减少轮询频率
          console.log('无活跃项目，将减少轮询频率')
        }
      } catch (error) {
        console.error('Polling error:', error)
      }
    }

    // 立即执行一次
    poll()
    
    // 设置定时器
    intervalRef.current = setInterval(poll, interval)
  }

  const stopPolling = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setIsPolling(false)
  }

  const refreshNow = async () => {
    try {
      const projects = await projectApi.getProjects()
      // 确保projects是数组类型
      const safeProjects = Array.isArray(projects) ? projects : []
      if (onProjectsUpdate) {
        onProjectsUpdate(safeProjects)
      }
      setLastUpdateTime(Date.now())
      return safeProjects
    } catch (error) {
      console.error('Manual refresh error:', error)
      throw error
    }
  }

  useEffect(() => {
    if (enabled) {
      startPolling()
    } else {
      stopPolling()
    }

    return () => {
      stopPolling()
    }
  }, [enabled, interval])

  return {
    isPolling,
    lastUpdateTime,
    startPolling,
    stopPolling,
    refreshNow
  }
}

export default useProjectPolling