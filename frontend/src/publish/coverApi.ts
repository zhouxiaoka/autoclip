import api from '../services/api'

export type CoverProvider = 'openai' | 'seedream' | 'dashscope'

export interface CoverConfigView {
  enabled: boolean
  provider: CoverProvider | string
  model: string
  api_key_masked: string
  base_url: string
  ocr_model: string
  allow_send_frame: boolean
  configured: boolean
  source: string
  note?: string | null
}

export interface CoverView {
  ok: boolean
  platform: string
  url?: string | null
  path?: string
  method?: string
  title?: string
  subtitle?: string
  badge?: string
  content_type?: string
  warning?: string | null
}

export interface CoverJobView {
  job_id: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | string
  error?: string
  result?: CoverView
}

export interface CoverGenerateBody {
  platform?: string
  title?: string
  subtitle?: string
  badge?: string
  content_type?: string
  force_local?: boolean
  sync?: boolean
}

export const coverApi = {
  getConfig: (): Promise<CoverConfigView> => api.get('/publish/covers/config'),
  saveConfig: (body: Partial<CoverConfigView> & { api_key?: string }): Promise<CoverConfigView & { ok?: boolean }> =>
    api.put('/publish/covers/config', body),
  clearConfig: (): Promise<CoverConfigView & { ok?: boolean }> => api.delete('/publish/covers/config'),
  get: (projectId: string, clipId: string, platform = 'bilibili'): Promise<CoverView> =>
    api.get(`/publish/covers/${projectId}/clips/${clipId}`, { params: { platform } }),
  start: (projectId: string, clipId: string, body: CoverGenerateBody = {}): Promise<{ ok: boolean; job_id: string; status: string } | CoverView> =>
    api.post(`/publish/covers/${projectId}/clips/${clipId}`, body),
  job: (jobId: string): Promise<CoverJobView> => api.get(`/publish/covers/jobs/${jobId}`),
  cancel: (jobId: string): Promise<CoverJobView> => api.post(`/publish/covers/jobs/${jobId}/cancel`),
}
