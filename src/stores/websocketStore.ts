/**
 * WebSocket状态管理Store
 * 使用Zustand管理WebSocket连接、消息和状态
 */

import { create } from 'zustand'
import { devtools } from 'zustand/middleware'

// WebSocket消息类型定义
export interface WebSocketMessage {
  type: 'task_update' | 'task_progress' | 'project_update' | 'system_notification' | 'error_notification'
  timestamp: string
  [key: string]: any
}

// 任务更新消息
export interface TaskUpdateMessage extends WebSocketMessage {
  type: 'task_update'
  task_id: string
  status: 'started' | 'processing' | 'completed' | 'failed'
  progress?: number
  message?: string
  error?: string
}

// 任务进度消息
export interface TaskProgressMessage extends WebSocketMessage {
  type: 'task_progress'
  task_id: string
  current_step: number
  total_steps: number
  step_name: string
  progress: number
  message?: string
  step_result?: Record<string, any>
}

// 项目更新消息
export interface ProjectUpdateMessage extends WebSocketMessage {
  type: 'project_update'
  project_id: string
  status: 'processing' | 'completed' | 'failed'
  progress?: number
  message?: string
}

// 系统通知消息
export interface SystemNotificationMessage extends WebSocketMessage {
  type: 'system_notification'
  notification_type: string
  title: string
  message: string
  level: 'info' | 'success' | 'warning' | 'error'
}

// 错误通知消息
export interface ErrorNotificationMessage extends WebSocketMessage {
  type: 'error_notification'
  error_type: string
  error_message: string
  details?: Record<string, any>
}

// WebSocket连接状态
export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'error'

// Store状态接口
interface WebSocketState {
  // 连接状态
  connectionStatus: ConnectionStatus
  socket: WebSocket | null
  reconnectAttempts: number
  maxReconnectAttempts: number
  reconnectInterval: number
  
  // 消息管理
  messages: WebSocketMessage[]
  unreadCount: number
  
  // 任务状态
  tasks: Record<string, TaskUpdateMessage>
  
  // 项目状态
  projects: Record<string, ProjectUpdateMessage>
  
  // 系统通知
  notifications: SystemNotificationMessage[]
  
  // 订阅主题
  subscribedTopics: Set<string>
  
  // Actions
  connect: (userId: string) => void
  disconnect: () => void
  reconnect: () => void
  sendMessage: (message: any) => void
  subscribeToTopic: (topic: string) => void
  unsubscribeFromTopic: (topic: string) => void
  clearMessages: () => void
  markAsRead: () => void
  removeNotification: (index: number) => void
  getTaskStatus: (taskId: string) => TaskUpdateMessage | null
  getProjectStatus: (projectId: string) => ProjectUpdateMessage | null
}

// WebSocket URL配置
const getWebSocketUrl = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}/api/ws`
}

export const useWebSocketStore = create<WebSocketState>()(devtools(
  (set, get) => ({
    // 初始状态
    connectionStatus: 'disconnected',
    socket: null,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    reconnectInterval: 3000,
    
    messages: [],
    unreadCount: 0,
    
    tasks: {},
    projects: {},
    notifications: [],
    
    subscribedTopics: new Set(),
    
    // 连接WebSocket
    connect: (userId: string) => {
      const state = get()
      
      if (state.socket && state.connectionStatus === 'connected') {
        console.log('WebSocket已连接，跳过重复连接')
        return
      }
      
      set({ connectionStatus: 'connecting' })
      
      try {
        const wsUrl = `${getWebSocketUrl()}/${userId}`
        const socket = new WebSocket(wsUrl)
        
        socket.onopen = () => {
          console.log('WebSocket连接已建立')
          set({ 
            connectionStatus: 'connected',
            socket,
            reconnectAttempts: 0
          })
        }
        
        socket.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data)
            
            set((state) => {
              const newState = {
                messages: [...state.messages, message],
                unreadCount: state.unreadCount + 1
              }
              
              // 根据消息类型更新相应状态
              switch (message.type) {
                case 'task_update':
                  const taskMsg = message as TaskUpdateMessage
                  newState.tasks = {
                    ...state.tasks,
                    [taskMsg.task_id]: taskMsg
                  }
                  break
                  
                case 'task_progress':
                  const progressMsg = message as TaskProgressMessage
                  // 更新任务进度信息
                  const existingTask = state.tasks[progressMsg.task_id]
                  newState.tasks = {
                    ...state.tasks,
                    [progressMsg.task_id]: {
                      ...existingTask,
                      type: 'task_update',
                      task_id: progressMsg.task_id,
                      status: 'processing',
                      progress: progressMsg.progress,
                      message: progressMsg.message || progressMsg.step_name,
                      timestamp: progressMsg.timestamp,
                      current_step: progressMsg.current_step,
                      total_steps: progressMsg.total_steps,
                      step_name: progressMsg.step_name,
                      step_result: progressMsg.step_result
                    } as TaskUpdateMessage & {
                      current_step: number
                      total_steps: number
                      step_name: string
                      step_result?: Record<string, any>
                    }
                  }
                  break
                  
                case 'project_update':
                  const projectMsg = message as ProjectUpdateMessage
                  newState.projects = {
                    ...state.projects,
                    [projectMsg.project_id]: projectMsg
                  }
                  break
                  
                case 'system_notification':
                  const notificationMsg = message as SystemNotificationMessage
                  newState.notifications = [...state.notifications, notificationMsg]
                  break
                  
                case 'error_notification':
                  const errorMsg = message as ErrorNotificationMessage
                  newState.notifications = [
                    ...state.notifications,
                    {
                      type: 'system_notification',
                      notification_type: 'error',
                      title: '错误',
                      message: errorMsg.error_message,
                      level: 'error',
                      timestamp: errorMsg.timestamp
                    } as SystemNotificationMessage
                  ]
                  break
              }
              
              return newState
            })
          } catch (error) {
            console.error('解析WebSocket消息失败:', error)
          }
        }
        
        socket.onclose = (event) => {
          console.log('WebSocket连接已关闭:', event.code, event.reason)
          set({ connectionStatus: 'disconnected', socket: null })
          
          // 自动重连
          const state = get()
          if (state.reconnectAttempts < state.maxReconnectAttempts) {
            setTimeout(() => {
              set((state) => ({ 
                connectionStatus: 'reconnecting',
                reconnectAttempts: state.reconnectAttempts + 1 
              }))
              get().connect(userId)
            }, state.reconnectInterval)
          } else {
            set({ connectionStatus: 'error' })
          }
        }
        
        socket.onerror = (error) => {
          console.error('WebSocket错误:', error)
          set({ connectionStatus: 'error' })
        }
        
      } catch (error) {
        console.error('创建WebSocket连接失败:', error)
        set({ connectionStatus: 'error' })
      }
    },
    
    // 断开连接
    disconnect: () => {
      const state = get()
      if (state.socket) {
        state.socket.close()
      }
      set({ 
        connectionStatus: 'disconnected',
        socket: null,
        reconnectAttempts: 0
      })
    },
    
    // 重新连接
    reconnect: () => {
      const state = get()
      state.disconnect()
      // 这里需要用户ID，实际使用时应该从认证状态获取
      setTimeout(() => state.connect('user'), 1000)
    },
    
    // 发送消息
    sendMessage: (message: any) => {
      const state = get()
      if (state.socket && state.connectionStatus === 'connected') {
        state.socket.send(JSON.stringify(message))
      } else {
        console.warn('WebSocket未连接，无法发送消息')
      }
    },
    
    // 订阅主题
    subscribeToTopic: (topic: string) => {
      const state = get()
      state.sendMessage({
        type: 'subscribe',
        topic
      })
      
      set((state) => ({
        subscribedTopics: new Set([...state.subscribedTopics, topic])
      }))
    },
    
    // 取消订阅主题
    unsubscribeFromTopic: (topic: string) => {
      const state = get()
      state.sendMessage({
        type: 'unsubscribe',
        topic
      })
      
      set((state) => {
        const newTopics = new Set(state.subscribedTopics)
        newTopics.delete(topic)
        return { subscribedTopics: newTopics }
      })
    },
    
    // 清空消息
    clearMessages: () => {
      set({ messages: [], unreadCount: 0 })
    },
    
    // 标记为已读
    markAsRead: () => {
      set({ unreadCount: 0 })
    },
    
    // 移除通知
    removeNotification: (index: number) => {
      set((state) => ({
        notifications: state.notifications.filter((_, i) => i !== index)
      }))
    },
    
    // 获取任务状态
    getTaskStatus: (taskId: string) => {
      return get().tasks[taskId] || null
    },
    
    // 获取项目状态
    getProjectStatus: (projectId: string) => {
      return get().projects[projectId] || null
    }
  }),
  {
    name: 'websocket-store',
    partialize: (state) => ({
      // 只持久化部分状态，不包括连接相关的状态
      notifications: state.notifications,
      subscribedTopics: Array.from(state.subscribedTopics)
    })
  }
))

// 导出便捷的hooks
export const useWebSocketConnection = () => {
  const { connectionStatus, connect, disconnect, reconnect } = useWebSocketStore()
  return { connectionStatus, connect, disconnect, reconnect }
}

export const useWebSocketMessages = () => {
  const { messages, unreadCount, clearMessages, markAsRead } = useWebSocketStore()
  return { messages, unreadCount, clearMessages, markAsRead }
}

export const useTaskStatus = (taskId: string) => {
  return useWebSocketStore((state) => state.getTaskStatus(taskId))
}

export const useProjectStatus = (projectId: string) => {
  return useWebSocketStore((state) => state.getProjectStatus(projectId))
}

export const useNotifications = () => {
  const { notifications, removeNotification } = useWebSocketStore()
  return { notifications, removeNotification }
}