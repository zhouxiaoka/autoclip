import api from '../services/api'

export interface UploadPostConfigView {
  configured: boolean
  source: string
  api_key_masked: string
  user: string
  note?: string | null
}

export interface UploadPostProfile {
  username: string
  connected_platforms: string[]
  reconnect_platforms?: string[]
}

export interface PlatformResult {
  platform: string
  success: boolean
  url?: string | null
  message?: string | null
  error?: string | null
  skipped?: boolean
  fallback_to_inbox?: boolean
}

export interface PublishJobView {
  job_id: string
  status: 'queued' | 'running' | 'submitted' | 'failed' | string
  error?: string
  request_id?: string
  remote?: {
    final?: boolean
    results?: PlatformResult[]
    message?: string
  }
}

export interface PublishClipBody {
  platforms: string[]
  user?: string
  preset?: string
  title?: string
  description?: string
  subtitles: boolean
  title_card: boolean
  scheduled_date?: string
  timezone?: string
  extra?: Record<string, string>
}

export interface PublishRecord {
  request_id: string
  job_id?: string | null
  clip_id?: string
  title?: string
  platforms?: string[]
  status?: string
  scheduled_date?: string | null
  submitted_at?: string
}

export const uploadPostApi = {
  getConfig: (): Promise<UploadPostConfigView> => api.get('/publish/upload-post/config'),
  saveConfig: (body: { api_key?: string; user?: string }): Promise<UploadPostConfigView & { ok?: boolean; account?: { email?: string; plan?: string } }> =>
    api.put('/publish/upload-post/config', body),
  clearConfig: (): Promise<{ ok: boolean; configured: boolean }> => api.delete('/publish/upload-post/config'),
  profiles: (): Promise<{ profiles: UploadPostProfile[] }> => api.get('/publish/upload-post/profiles'),
  start: (projectId: string, clipId: string, body: PublishClipBody): Promise<{ ok: boolean; job_id: string; status: string }> =>
    api.post(`/publish/upload-post/${projectId}/clips/${clipId}`, body),
  job: (jobId: string): Promise<PublishJobView> => api.get(`/publish/upload-post/jobs/${jobId}`),
  records: (projectId: string): Promise<{ records: PublishRecord[] }> => api.get(`/publish/upload-post/${projectId}/records`),
  cancel: (projectId: string, requestId: string): Promise<{ ok: boolean; status: string }> =>
    api.delete(`/publish/upload-post/${projectId}/records/${requestId}`),
}
