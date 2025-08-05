/**
 * WebSocket连接提供者组件
 * 管理WebSocket连接生命周期和自动重连
 */

import React, { useEffect, useRef } from 'react'
import { useWebSocketStore, TaskProgressMessage } from '../stores/websocketStore'
import { toast } from 'sonner'
import { CheckCircle, AlertCircle, Activity } from 'lucide-react'

interface WebSocketProviderProps {
  children: React.ReactNode
  userId?: string
  autoConnect?: boolean
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({
  children,
  userId = 'user', // 默认用户ID，实际应用中应该从认证状态获取
  autoConnect = true
}) => {
  const {
    connectionStatus,
    connect,
    disconnect,
    notifications,
    removeNotification
  } = useWebSocketStore()
  
  const hasConnected = useRef(false)
  const notificationTimeouts = useRef<Map<number, NodeJS.Timeout>>(new Map())
  
  // 自动连接
  useEffect(() => {
    if (autoConnect && !hasConnected.current && connectionStatus === 'disconnected') {
      connect(userId)
      hasConnected.current = true
    }
    
    // 组件卸载时断开连接
    return () => {
      if (hasConnected.current) {
        disconnect()
        hasConnected.current = false
      }
    }
  }, [autoConnect, userId, connectionStatus, connect, disconnect])
  
  // 显示连接状态变化的提示
  useEffect(() => {
    switch (connectionStatus) {
      case 'connected':
        toast.success('WebSocket连接已建立')
        break
      case 'disconnected':
        if (hasConnected.current) {
          toast.error('WebSocket连接已断开')
        }
        break
      case 'reconnecting':
        toast.loading('正在重新连接...')
        break
      case 'error':
        toast.error('WebSocket连接失败')
        break
    }
  }, [connectionStatus])
  
  // 处理WebSocket消息并显示通知
  useEffect(() => {
    const handleMessage = (message: any) => {
      // 根据消息类型显示不同的通知
      switch (message.type) {
        case 'task_update':
          if (message.status === 'completed') {
            toast.success(`任务完成: ${message.message || '处理完成'}`, {
              icon: <CheckCircle className="w-4 h-4" />
            })
          } else if (message.status === 'failed') {
            toast.error(`任务失败: ${message.error || '处理失败'}`, {
              icon: <AlertCircle className="w-4 h-4" />
            })
          } else if (message.status === 'started') {
            toast.info(`任务开始: ${message.message || '开始处理'}`, {
              icon: <Activity className="w-4 h-4" />
            })
          }
          break
          
        case 'task_progress':
          // 对于进度更新，只在特定里程碑显示通知
          const progressMsg = message as TaskProgressMessage
          if (progressMsg.current_step === 1 || progressMsg.progress >= 100 || progressMsg.progress % 25 === 0) {
            toast.info(`${progressMsg.step_name}: ${Math.round(progressMsg.progress)}%`, {
              icon: <Activity className="w-4 h-4" />,
              description: `步骤 ${progressMsg.current_step}/${progressMsg.total_steps}`
            })
          }
          break
          
        case 'project_update':
          if (message.status === 'completed') {
            toast.success(`项目完成: ${message.message || '项目处理完成'}`, {
              icon: <CheckCircle className="w-4 h-4" />
            })
          } else if (message.status === 'failed') {
            toast.error(`项目失败: ${message.message || '项目处理失败'}`, {
              icon: <AlertCircle className="w-4 h-4" />
            })
          }
          break
          
        case 'system_notification':
          const level = message.level || 'info'
          const toastFn = level === 'error' ? toast.error : 
                         level === 'warning' ? toast.warning :
                         level === 'success' ? toast.success : toast.info
          
          toastFn(message.message, {
            description: message.title
          })
          break
      }
    }
    
    // 监听新消息
    const unsubscribe = useWebSocketStore.subscribe(
      (state) => state.messages,
      (messages) => {
        if (messages.length > 0) {
          const latestMessage = messages[messages.length - 1]
          handleMessage(latestMessage)
        }
      }
    )
    
    return unsubscribe
  }, [])
  
  // 显示系统通知
  useEffect(() => {
    notifications.forEach((notification, index) => {
      // 避免重复显示同一个通知
      if (!notificationTimeouts.current.has(index)) {
        const { title, message, level } = notification
        
        // 根据级别显示不同类型的toast
        switch (level) {
          case 'success':
            toast.success(title, { description: message })
            break
          case 'error':
            toast.error(title, { description: message })
            break
          case 'warning':
            toast.warning(title, { description: message })
            break
          default:
            toast.info(title, { description: message })
        }
        
        // 设置自动移除通知的定时器
        const timeout = setTimeout(() => {
          removeNotification(index)
          notificationTimeouts.current.delete(index)
        }, 5000) // 5秒后自动移除
        
        notificationTimeouts.current.set(index, timeout)
      }
    })
    
    // 清理过期的定时器
    return () => {
      notificationTimeouts.current.forEach(timeout => clearTimeout(timeout))
      notificationTimeouts.current.clear()
    }
  }, [notifications, removeNotification])
  
  return <>{children}</>
}

/**
 * WebSocket连接状态指示器组件
 */
export const WebSocketStatusIndicator: React.FC = () => {
  const { connectionStatus, reconnect } = useWebSocketStore()
  
  const getStatusColor = () => {
    switch (connectionStatus) {
      case 'connected':
        return 'text-green-500'
      case 'connecting':
      case 'reconnecting':
        return 'text-yellow-500'
      case 'disconnected':
      case 'error':
        return 'text-red-500'
      default:
        return 'text-gray-500'
    }
  }
  
  const getStatusText = () => {
    switch (connectionStatus) {
      case 'connected':
        return '已连接'
      case 'connecting':
        return '连接中'
      case 'reconnecting':
        return '重连中'
      case 'disconnected':
        return '已断开'
      case 'error':
        return '连接错误'
      default:
        return '未知状态'
    }
  }
  
  return (
    <div className="flex items-center space-x-2 text-sm">
      <div className={`w-2 h-2 rounded-full ${getStatusColor().replace('text-', 'bg-')}`} />
      <span className={getStatusColor()}>{getStatusText()}</span>
      {(connectionStatus === 'disconnected' || connectionStatus === 'error') && (
        <button
          onClick={reconnect}
          className="text-blue-500 hover:text-blue-700 underline"
        >
          重连
        </button>
      )}
    </div>
  )
}

/**
 * 任务进度监控组件
 */
interface TaskProgressMonitorProps {
  taskId: string
  onComplete?: (result: any) => void
  onError?: (error: string) => void
}

export const TaskProgressMonitor: React.FC<TaskProgressMonitorProps> = ({
  taskId,
  onComplete,
  onError
}) => {
  const { subscribeToTopic, unsubscribeFromTopic, getTaskStatus } = useWebSocketStore()
  
  const taskStatus = getTaskStatus(taskId)
  
  useEffect(() => {
    // 订阅任务主题
    const topic = `task_${taskId}`
    subscribeToTopic(topic)
    
    return () => {
      unsubscribeFromTopic(topic)
    }
  }, [taskId, subscribeToTopic, unsubscribeFromTopic])
  
  useEffect(() => {
    if (taskStatus) {
      if (taskStatus.status === 'completed' && onComplete) {
        onComplete(taskStatus)
      } else if (taskStatus.status === 'failed' && onError) {
        onError(taskStatus.error || '任务执行失败')
      }
    }
  }, [taskStatus, onComplete, onError])
  
  if (!taskStatus) {
    return (
      <div className="flex items-center space-x-2">
        <div className="w-4 h-4 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
        <span className="text-gray-500">等待任务状态...</span>
      </div>
    )
  }
  
  const extendedTask = taskStatus as any
  
  return (
    <div className="space-y-2">
      <div className="flex items-center space-x-2 text-sm">
        {taskStatus.status === 'processing' ? (
          <Activity className="w-4 h-4 animate-spin text-blue-500" />
        ) : taskStatus.status === 'completed' ? (
          <CheckCircle className="w-4 h-4 text-green-500" />
        ) : taskStatus.status === 'failed' ? (
          <AlertCircle className="w-4 h-4 text-red-500" />
        ) : (
          <div className="w-4 h-4 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
        )}
        <span className="font-medium">
          {taskStatus.message || '处理中...'}
        </span>
        {taskStatus.progress !== undefined && (
          <span className="text-blue-600 font-medium">
            {Math.round(taskStatus.progress)}%
          </span>
        )}
      </div>
      
      {/* 显示步骤信息 */}
      {extendedTask.current_step && extendedTask.total_steps && (
        <div className="text-xs text-gray-500">
          步骤 {extendedTask.current_step}/{extendedTask.total_steps}: {extendedTask.step_name}
        </div>
      )}
      
      {/* 进度条 */}
      {taskStatus.progress !== undefined && (
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all duration-300"
            style={{ width: `${Math.min(100, Math.max(0, taskStatus.progress))}%` }}
          />
        </div>
      )}
      
      {taskStatus.status === 'failed' && taskStatus.error && (
        <div className="text-red-500 text-sm">
          错误: {taskStatus.error}
        </div>
      )}
    </div>
  )
}

/**
 * 项目进度监控组件
 */
interface ProjectProgressMonitorProps {
  projectId: string
  onComplete?: (result: any) => void
  onError?: (error: string) => void
}

export const ProjectProgressMonitor: React.FC<ProjectProgressMonitorProps> = ({
  projectId,
  onComplete,
  onError
}) => {
  const { subscribeToTopic, unsubscribeFromTopic, getProjectStatus } = useWebSocketStore()
  
  const projectStatus = getProjectStatus(projectId)
  
  useEffect(() => {
    // 订阅项目主题
    const topic = `project_${projectId}`
    subscribeToTopic(topic)
    
    return () => {
      unsubscribeFromTopic(topic)
    }
  }, [projectId, subscribeToTopic, unsubscribeFromTopic])
  
  useEffect(() => {
    if (projectStatus) {
      if (projectStatus.status === 'completed' && onComplete) {
        onComplete(projectStatus)
      } else if (projectStatus.status === 'failed' && onError) {
        onError(projectStatus.message || '项目处理失败')
      }
    }
  }, [projectStatus, onComplete, onError])
  
  if (!projectStatus) {
    return (
      <div className="flex items-center space-x-2">
        <div className="w-4 h-4 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
        <span className="text-gray-500">等待项目状态...</span>
      </div>
    )
  }
  
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">
          {projectStatus.message || '处理中...'}
        </span>
        <span className="text-sm text-gray-500">
          {projectStatus.progress || 0}%
        </span>
      </div>
      
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className="bg-green-500 h-2 rounded-full transition-all duration-300"
          style={{ width: `${projectStatus.progress || 0}%` }}
        />
      </div>
      
      {projectStatus.status === 'failed' && (
        <div className="text-red-500 text-sm">
          错误: {projectStatus.message}
        </div>
      )}
    </div>
  )
}