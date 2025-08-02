import axios from 'axios'
import { Project, Clip, Collection } from '../store/useProjectStore'

const api = axios.create({
  baseURL: 'http://localhost:8000/api', // FastAPI后端服务器地址
  timeout: 300000, // 增加到5分钟超时
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    console.error('API Error:', error)
    
    // 特殊处理429错误（系统繁忙）
    if (error.response?.status === 429) {
      const message = error.response?.data?.detail || '系统正在处理其他项目，请稍后再试'
      error.userMessage = message
    }
    // 处理超时错误
    else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      error.userMessage = '请求超时，项目可能仍在后台处理中，请稍后查看项目状态'
    }
    // 处理网络错误
    else if (error.code === 'NETWORK_ERROR' || !error.response) {
      error.userMessage = '网络连接失败，请检查网络连接'
    }
    // 处理服务器错误
    else if (error.response?.status >= 500) {
      error.userMessage = '服务器内部错误，请稍后重试'
    }
    
    return Promise.reject(error)
  }
)

export interface UploadFilesRequest {
  video_file: File
  srt_file?: File
  project_name: string
  video_category?: string
}

export interface VideoCategory {
  value: string
  name: string
  description: string
  icon: string
  color: string
}

export interface VideoCategoriesResponse {
  categories: VideoCategory[]
  default_category: string
}

export interface ProcessingStatus {
  status: 'processing' | 'completed' | 'error'
  current_step: number
  total_steps: number
  step_name: string
  progress: number
  error_message?: string
}

// B站相关接口类型
export interface BilibiliVideoInfo {
  title: string
  description: string
  duration: number
  uploader: string
  upload_date: string
  view_count: number
  like_count: number
  thumbnail: string
  url: string
}

export interface BilibiliDownloadRequest {
  url: string
  project_name: string
  video_category?: string
  browser?: string
}

export interface BilibiliDownloadTask {
  task_id: string
  url: string
  project_name: string
  video_category?: string
  browser?: string
  status: 'pending' | 'downloading' | 'completed' | 'failed'
  progress: number
  error_message?: string
  video_info?: BilibiliVideoInfo
  project_id?: string
  created_at: string
  updated_at: string
}

// 设置相关API
export const settingsApi = {
  // 获取系统配置
  getSettings: (): Promise<unknown> => {
    return api.get('/settings')
  },

  // 更新系统配置
  updateSettings: (settings: unknown): Promise<unknown> => {
    return api.post('/settings', settings)
  },

  // 测试API密钥
  testApiKey: (apiKey: string): Promise<{ success: boolean; error?: string }> => {
    return api.post('/settings/test-api-key', { api_key: apiKey })
  }
}

// 项目相关API
export const projectApi = {
  // 获取视频分类配置
  getVideoCategories: async (): Promise<VideoCategoriesResponse> => {
    return api.get('/video-categories')
  },

  // 获取所有项目
  getProjects: async (): Promise<Project[]> => {
    return api.get('/projects')
  },

  // 获取单个项目
  getProject: async (id: string): Promise<Project> => {
    return api.get(`/projects/${id}`)
  },

  // 上传文件并创建项目
  uploadFiles: async (data: UploadFilesRequest): Promise<Project> => {
    const formData = new FormData()
    formData.append('video_file', data.video_file)
    if (data.srt_file) {
      formData.append('srt_file', data.srt_file)
    }
    formData.append('project_name', data.project_name)
    if (data.video_category) {
      formData.append('video_category', data.video_category)
    }
    
    return api.post('/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  // 删除项目
  deleteProject: async (id: string): Promise<void> => {
    await api.delete(`/projects/${id}`)
  },

  // 开始处理项目
  startProcessing: async (id: string): Promise<void> => {
    await api.post(`/projects/${id}/process`)
  },

  // 重试处理项目
  retryProcessing: async (id: string): Promise<void> => {
    await api.post(`/projects/${id}/retry`)
  },

  // 获取处理状态
  getProcessingStatus: async (id: string): Promise<ProcessingStatus> => {
    return api.get(`/projects/${id}/status`)
  },

  // 获取项目日志
  getProjectLogs: async (id: string, lines: number = 50): Promise<{logs: Array<{timestamp: string, module: string, level: string, message: string}>}> => {
    return api.get(`/projects/${id}/logs?lines=${lines}`)
  },

  // 重启指定步骤
  restartStep: async (id: string, step: number): Promise<void> => {
    await api.post(`/projects/${id}/restart-step`, { step })
  },

  // 更新切片信息
  updateClip: (projectId: string, clipId: string, updates: Partial<Clip>): Promise<Clip> => {
    return api.patch(`/projects/${projectId}/clips/${clipId}`, updates)
  },

  // 创建合集
  createCollection: (projectId: string, collectionData: { collection_title: string, collection_summary: string, clip_ids: string[] }): Promise<Collection> => {
    return api.post(`/projects/${projectId}/collections`, collectionData)
  },

  // 更新合集信息
  updateCollection: (projectId: string, collectionId: string, updates: Partial<Collection>): Promise<Collection> => {
    return api.patch(`/projects/${projectId}/collections/${collectionId}`, updates)
  },

  // 删除合集
  deleteCollection: (projectId: string, collectionId: string): Promise<{message: string, deleted_collection: string}> => {
    return api.delete(`/projects/${projectId}/collections/${collectionId}`)
  },

  // 下载切片视频
  downloadClip: (projectId: string, clipId: string): Promise<Blob> => {
    return api.get(`/projects/${projectId}/clips/${clipId}/download`, {
      responseType: 'blob'
    })
  },

  // 下载合集视频
  downloadCollection: (projectId: string, collectionId: string): Promise<Blob> => {
    return api.get(`/projects/${projectId}/collections/${collectionId}/download`, {
      responseType: 'blob'
    })
  },

  // 导出元数据
  exportMetadata: (projectId: string): Promise<Blob> => {
    return api.get(`/projects/${projectId}/export`, {
      responseType: 'blob'
    })
  },

  // 生成合集视频
  generateCollectionVideo: (projectId: string, collectionId: string) => {
    return api.post(`/projects/${projectId}/collections/${collectionId}/generate`)
  },

  downloadVideo: async (projectId: string, clipId?: string, collectionId?: string) => {
    let url = `/projects/${projectId}/download`
    if (clipId) {
      url += `?clip_id=${clipId}`
    } else if (collectionId) {
      url += `?collection_id=${collectionId}`
    }
    
    try {
      // 对于blob类型的响应，需要直接使用axios而不是经过拦截器
      const response = await axios.get(`http://localhost:8000/api${url}`, { 
        responseType: 'blob',
        headers: {
          'Accept': 'application/octet-stream'
        }
      })
      
      // 从响应头获取文件名，如果没有则使用默认名称
      const contentDisposition = response.headers['content-disposition']
      let filename = clipId ? `clip_${clipId}.mp4` : 
                     collectionId ? `collection_${collectionId}.mp4` : 
                     `project_${projectId}.mp4`
      
      if (contentDisposition) {
        // 优先尝试解析 RFC 6266 格式的 filename* 参数
        const filenameStarMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/)
        if (filenameStarMatch) {
          filename = decodeURIComponent(filenameStarMatch[1])
        } else {
          // 回退到传统的 filename 参数
          const filenameMatch = contentDisposition.match(/filename="([^"]+)"/)
          if (filenameMatch) {
            filename = filenameMatch[1]
          }
        }
      }
      
      // 创建下载链接
      const blob = new Blob([response.data], { type: 'video/mp4' })
      const downloadUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = filename
      
      // 触发下载
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(downloadUrl)
      
      return response.data
    } catch (error) {
      console.error('下载失败:', error)
      throw error
    }
  },

  // 打包下载项目的所有文件
  downloadProjectAll: async (projectId: string) => {
    try {
      const response = await axios.get(`http://localhost:8000/api/projects/${projectId}/download-all`, { 
        responseType: 'blob',
        headers: {
          'Accept': 'application/zip'
        }
      })
      
      // 从响应头获取文件名
      const contentDisposition = response.headers['content-disposition']
      let filename = `project_${projectId}_完整项目.zip`
      
      if (contentDisposition) {
        const filenameStarMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/)
        if (filenameStarMatch) {
          filename = decodeURIComponent(filenameStarMatch[1])
        } else {
          const filenameMatch = contentDisposition.match(/filename="([^"]+)"/)
          if (filenameMatch) {
            filename = filenameMatch[1]
          }
        }
      }
      
      // 创建下载链接
      const blob = new Blob([response.data], { type: 'application/zip' })
      const downloadUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = filename
      
      // 触发下载
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(downloadUrl)
      
      return response.data
    } catch (error) {
      console.error('打包下载失败:', error)
      throw error
    }
  },

  // 获取项目独立的文件URL
  getProjectFileUrl: (projectId: string, filePath: string): string => {
    return `http://localhost:8000/api/projects/${projectId}/files/${filePath}`
  },

  // 获取切片视频URL
  getClipVideoUrl: (projectId: string, clipId: string): string => {
    // 直接使用clipId，让后端处理文件查找
    return `http://localhost:8000/api/projects/${projectId}/clips/${clipId}`
  },

  // 获取合集视频URL
  getCollectionVideoUrl: (projectId: string, collectionId: string): string => {
    return `http://localhost:8000/api/projects/${projectId}/files/output/collections/${collectionId}.mp4`
  }
}

// B站相关API
export const bilibiliApi = {
  // 解析B站视频信息
  parseVideoInfo: async (url: string, browser?: string): Promise<{success: boolean, video_info: BilibiliVideoInfo}> => {
    const formData = new FormData()
    formData.append('url', url)
    if (browser) {
      formData.append('browser', browser)
    }
    return api.post('/bilibili/parse', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  // 创建B站下载任务
  createDownloadTask: async (data: BilibiliDownloadRequest): Promise<BilibiliDownloadTask> => {
    return api.post('/bilibili/download', data)
  },

  // 获取下载任务状态
  getTaskStatus: async (taskId: string): Promise<BilibiliDownloadTask> => {
    return api.get(`/bilibili/tasks/${taskId}`)
  },

  // 获取所有下载任务
  getAllTasks: async (): Promise<BilibiliDownloadTask[]> => {
    return api.get('/bilibili/tasks')
  }
}

// 系统状态相关API
export const systemApi = {
  // 获取系统状态
  getSystemStatus: (): Promise<{
    current_processing_count: number
    max_concurrent_processing: number
    total_projects: number
    processing_projects: string[]
  }> => {
    return api.get('/system/status')
  }
}

export default api