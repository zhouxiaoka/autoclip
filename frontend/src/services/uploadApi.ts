import { t } from '../i18n'
/**
 * 投稿相关API服务
 */

import api from './api'

// 类型定义
export interface BilibiliAccount {
  id: string
  username: string
  nickname?: string
  status: string
  is_default: boolean
  created_at: string
}

export interface UploadRequest {
  clip_ids: string[]
  account_id: string
  title: string
  description: string
  tags: string[]
  partition_id: number
}

export interface UploadRecord {
  id: string | number
  task_id?: string
  project_id?: string
  account_id: string | number
  clip_id: string
  title: string
  description?: string
  tags?: string
  partition_id: number
  video_path?: string
  bv_id?: string
  av_id?: string
  status: string
  error_message?: string
  progress: number
  file_size?: number
  upload_duration?: number
  created_at: string
  updated_at: string
  account_username?: string
  account_nickname?: string
  project_name?: string
}

export interface UploadStatus {
  id: string
  status: string
  bvid?: string
  error_message?: string
  created_at: string
}

// B站分区信息 - 根据官方API文档更新，一级主分区
export const BILIBILI_PARTITIONS = [
  { id: 1, get name() { return t("动画") } },
  { id: 4, get name() { return t("游戏") } },
  { id: 8, get name() { return t("鬼畜") } },
  { id: 3, get name() { return t("音乐") } },
  { id: 129, get name() { return t("舞蹈") } },
  { id: 181, get name() { return t("影视") } },
  { id: 5, get name() { return t("娱乐") } },
  { id: 36, get name() { return t("知识") } },
  { id: 188, get name() { return t("科技数码") } },
  { id: 202, get name() { return t("资讯") } },
  { id: 76, get name() { return t("美食") } },
  { id: 138, get name() { return t("小剧场") } },
  { id: 176, get name() { return t("汽车") } },
  { id: 155, get name() { return t("时尚美妆") } },
  { id: 235, get name() { return t("体育运动") } },
  { id: 75, get name() { return t("动物") } },
  { id: 21, name: "vlog" },
  { id: 162, get name() { return t("绘画") } },
  { id: 207, get name() { return t("人工智能") } },
  { id: 208, get name() { return t("家装房产") } },
  { id: 209, get name() { return t("户外潮流") } },
  { id: 164, get name() { return t("健身") } },
  { id: 161, get name() { return t("手工") } },
  { id: 165, get name() { return t("旅游出行") } },
  { id: 158, get name() { return t("三农") } },
  { id: 159, get name() { return t("亲子") } },
  { id: 160, get name() { return t("健康") } },
  { id: 163, get name() { return t("情感") } },
  { id: 22, get name() { return t("生活兴趣") } },
  { id: 23, get name() { return t("生活经验") } }
]

// 投稿API
export const uploadApi = {
  // 账号管理
  createAccount: async (username: string, password: string, nickname?: string, cookieContent?: string): Promise<BilibiliAccount> => {
    return api.post('/upload/accounts', { username, password, nickname, cookie_content: cookieContent })
  },

  // 获取支持的登录方式
  getLoginMethods: async (): Promise<{methods: Array<{
    id: string,
    name: string,
    description: string,
    icon: string,
    recommended: boolean,
    risk_level: string
  }>}> => {
    return api.get('/upload/login-methods')
  },

  // 账号密码登录
  passwordLogin: async (username: string, password: string, nickname?: string): Promise<BilibiliAccount> => {
    return api.post('/upload/password-login', { username, password, nickname })
  },

  // Cookie导入登录
  cookieLogin: async (cookies: Record<string, string>, nickname?: string): Promise<BilibiliAccount> => {
    return api.post('/upload/cookie-login', { cookies, nickname })
  },

  // 第三方登录
  thirdPartyLogin: async (type: 'wechat' | 'qq', nickname?: string): Promise<{login_url: string, message: string}> => {
    return api.post('/upload/third-party-login', { type, nickname })
  },

  startQRLogin: async (nickname?: string): Promise<{session_id: string, status: string, message: string}> => {
    return api.post('/upload/qr-login', { nickname })
  },

  checkQRLoginStatus: async (sessionId: string): Promise<{session_id: string, status: string, message: string, qr_code?: string}> => {
    return api.get(`/upload/qr-login/${sessionId}`)
  },

  completeQRLogin: async (sessionId: string, nickname?: string): Promise<BilibiliAccount> => {
    return api.post(`/upload/qr-login/${sessionId}/complete`, { nickname })
  },

  getAccounts: async (): Promise<BilibiliAccount[]> => {
    return api.get('/upload/accounts')
  },

  deleteAccount: async (accountId: string): Promise<void> => {
    return api.delete(`/upload/accounts/${accountId}`)
  },

  checkAccountStatus: async (accountId: string): Promise<{is_valid: boolean, message: string}> => {
    return api.post(`/upload/accounts/${accountId}/check`)
  },

  // 投稿管理
  createUploadTask: async (projectId: string, uploadData: UploadRequest): Promise<{message: string, record_id: string, clip_count: number}> => {
    return api.post(`/upload/projects/${projectId}/upload`, uploadData)
  },

  retryUploadTask: async (recordId: string): Promise<{message: string}> => {
    return api.post(`/upload/records/${recordId}/retry`)
  },

  cancelUploadTask: async (recordId: string): Promise<{message: string}> => {
    return api.post(`/upload/records/${recordId}/cancel`)
  },

  getUploadRecords: async (projectId?: string): Promise<UploadRecord[]> => {
    const params = projectId ? { project_id: projectId } : {}
    return api.get('/upload/records', { params })
  },

  getUploadRecord: async (recordId: string): Promise<UploadStatus> => {
    return api.get(`/upload/records/${recordId}`)
  },

  getBilibiliAccounts: async (): Promise<BilibiliAccount[]> => {
    return api.get('/upload/accounts')
  },

  // 投稿任务管理
  retryUpload: async (recordId: string | number): Promise<{message: string}> => {
    return api.post(`/upload/records/${recordId}/retry`)
  },

  cancelUpload: async (recordId: string | number): Promise<{message: string}> => {
    return api.post(`/upload/records/${recordId}/cancel`)
  },

  deleteUpload: async (recordId: string | number): Promise<{message: string}> => {
    return api.delete(`/upload/records/${recordId}`)
  }
}
