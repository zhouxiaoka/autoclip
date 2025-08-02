import { useEffect, useRef, useState } from 'react'
import { projectApi } from '../services/api'
import { Project, useProjectStore } from '../store/useProjectStore'

interface UseProjectPollingOptions {
  interval?: number // 轮询间隔，默认10秒
  onProjectsUpdate?: (projects: Project[]) => void
  enabled?: boolean // 是否启用轮询
}

export const useProjectPolling = ({
  interval = 10000,
  onProjectsUpdate,
  enabled = true
}: UseProjectPollingOptions = {}) => {
  const [isPolling, setIsPolling] = useState(false)
  const intervalRef = useRef<number | null>(null)
  const [lastUpdateTime, setLastUpdateTime] = useState<number>(Date.now())
  const isDragging = useProjectStore(state => state.isDragging)

  const startPolling = () => {
    if (!enabled || intervalRef.current) return

    setIsPolling(true)
    
    const poll = async () => {
      try {
        // 如果正在拖拽，跳过这次轮询
        if (isDragging) {
          console.log('Skipping poll: dragging in progress')
          return
        }
        
        const projects = await projectApi.getProjects()
        const hasProcessingProjects = projects.some(p => p.status === 'processing')
        
        if (onProjectsUpdate) {
          onProjectsUpdate(projects)
        }
        
        setLastUpdateTime(Date.now())
        
        // 如果没有正在处理的项目，可以适当减少轮询频率
        if (!hasProcessingProjects) {
          // 可以在这里实现动态调整轮询频率的逻辑
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
      if (onProjectsUpdate) {
        onProjectsUpdate(projects)
      }
      setLastUpdateTime(Date.now())
      return projects
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