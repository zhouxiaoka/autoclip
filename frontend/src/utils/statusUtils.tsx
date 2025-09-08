/**
 * 统一的状态处理工具
 * 解决前端项目中状态处理不一致的问题
 */

import { 
  ClockCircleOutlined, 
  LoadingOutlined, 
  CheckCircleOutlined, 
  ExclamationCircleOutlined,
  CloseCircleOutlined,
  PlayCircleOutlined
} from '@ant-design/icons'

// 统一的状态类型定义
export type ProjectStatus = 'pending' | 'processing' | 'completed' | 'failed'
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
export type UploadStatus = 'pending' | 'processing' | 'success' | 'failed'

// 项目状态配置
export interface ProjectStatusConfig {
  color: string
  icon: any
  text: string
  badgeStatus: 'default' | 'processing' | 'success' | 'error'
  backgroundColor: string
  borderColor: string
}

// 任务状态配置
export interface TaskStatusConfig {
  color: string
  icon: any
  text: string
  badgeStatus: 'default' | 'processing' | 'success' | 'error'
}

// 上传状态配置
export interface UploadStatusConfig {
  color: string
  icon: any
  text: string
  badgeStatus: 'default' | 'processing' | 'success' | 'error'
}

/**
 * 获取项目状态配置
 */
export const getProjectStatusConfig = (status: ProjectStatus): ProjectStatusConfig => {
  switch (status) {
    case 'pending':
      return {
        color: '#1890ff',
        icon: ClockCircleOutlined,
        text: '等待中',
        badgeStatus: 'processing',
        backgroundColor: 'rgba(217, 217, 217, 0.15)',
        borderColor: 'rgba(217, 217, 217, 0.3)'
      }
    case 'processing':
      return {
        color: '#1890ff',
        icon: LoadingOutlined,
        text: '处理中',
        badgeStatus: 'processing',
        backgroundColor: 'rgba(24, 144, 255, 0.15)',
        borderColor: 'rgba(24, 144, 255, 0.3)'
      }
    case 'completed':
      return {
        color: '#52c41a',
        icon: CheckCircleOutlined,
        text: '已完成',
        badgeStatus: 'success',
        backgroundColor: 'rgba(82, 196, 26, 0.15)',
        borderColor: 'rgba(82, 196, 26, 0.3)'
      }
    case 'failed':
      return {
        color: '#ff4d4f',
        icon: ExclamationCircleOutlined,
        text: '失败',
        badgeStatus: 'error',
        backgroundColor: 'rgba(255, 77, 79, 0.15)',
        borderColor: 'rgba(255, 77, 79, 0.3)'
      }
    default:
      return {
        color: '#d9d9d9',
        icon: ClockCircleOutlined,
        text: '未知状态',
        badgeStatus: 'default',
        backgroundColor: 'rgba(217, 217, 217, 0.15)',
        borderColor: 'rgba(217, 217, 217, 0.3)'
      }
  }
}

/**
 * 获取任务状态配置
 */
export const getTaskStatusConfig = (status: TaskStatus): TaskStatusConfig => {
  switch (status) {
    case 'pending':
      return {
        color: '#1890ff',
        icon: ClockCircleOutlined,
        text: '等待中',
        badgeStatus: 'processing'
      }
    case 'running':
      return {
        color: '#1890ff',
        icon: PlayCircleOutlined,
        text: '执行中',
        badgeStatus: 'processing'
      }
    case 'completed':
      return {
        color: '#52c41a',
        icon: CheckCircleOutlined,
        text: '已完成',
        badgeStatus: 'success'
      }
    case 'failed':
      return {
        color: '#ff4d4f',
        icon: CloseCircleOutlined,
        text: '失败',
        badgeStatus: 'error'
      }
    case 'cancelled':
      return {
        color: '#d9d9d9',
        icon: CloseCircleOutlined,
        text: '已取消',
        badgeStatus: 'default'
      }
    default:
      return {
        color: '#d9d9d9',
        icon: ClockCircleOutlined,
        text: '未知状态',
        badgeStatus: 'default'
      }
  }
}

/**
 * 获取上传状态配置
 */
export const getUploadStatusConfig = (status: UploadStatus): UploadStatusConfig => {
  switch (status) {
    case 'pending':
      return {
        color: '#1890ff',
        icon: ClockCircleOutlined,
        text: '待处理',
        badgeStatus: 'processing'
      }
    case 'processing':
      return {
        color: '#1890ff',
        icon: LoadingOutlined,
        text: '处理中',
        badgeStatus: 'processing'
      }
    case 'success':
      return {
        color: '#52c41a',
        icon: CheckCircleOutlined,
        text: '成功',
        badgeStatus: 'success'
      }
    case 'failed':
      return {
        color: '#ff4d4f',
        icon: CloseCircleOutlined,
        text: '失败',
        badgeStatus: 'error'
      }
    default:
      return {
        color: '#d9d9d9',
        icon: ClockCircleOutlined,
        text: '未知状态',
        badgeStatus: 'default'
      }
  }
}

/**
 * 获取进度条状态
 */
export const getProgressStatus = (status: ProjectStatus | TaskStatus | UploadStatus): 'normal' | 'active' | 'success' | 'exception' => {
  switch (status) {
    case 'processing':
    case 'running':
      return 'active'
    case 'completed':
    case 'success':
      return 'success'
    case 'failed':
      return 'exception'
    default:
      return 'normal'
  }
}

/**
 * 计算项目进度百分比
 */
export const calculateProjectProgress = (
  status: ProjectStatus, 
  currentStep?: number, 
  totalSteps?: number
): number => {
  if (status === 'completed') return 100
  if (status === 'failed') return 0
  if (currentStep && totalSteps && totalSteps > 0) {
    return Math.round((currentStep / totalSteps) * 100)
  }
  return 0
}

/**
 * 状态兼容性转换
 * 将旧的状态值转换为新的统一状态值
 */
export const normalizeProjectStatus = (status: string): ProjectStatus => {
  switch (status) {
    case 'error':
      return 'failed'
    case 'pending':
    case 'processing':
    case 'completed':
    case 'failed':
      return status as ProjectStatus
    default:
      return 'pending'
  }
}

export const normalizeTaskStatus = (status: string): TaskStatus => {
  switch (status) {
    case 'pending':
    case 'running':
    case 'completed':
    case 'failed':
    case 'cancelled':
      return status as TaskStatus
    default:
      return 'pending'
  }
}
