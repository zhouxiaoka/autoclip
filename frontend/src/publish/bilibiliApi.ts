import api from '../services/api'
import type { PlatformResult } from './uploadPostApi'

export interface BilibiliConfigView {
  configured: boolean
  source: string
  nickname: string
  uid: string
  note?: string | null
}

export interface BilibiliJobView {
  job_id: string
  status: 'queued' | 'running' | 'completed' | 'scheduled' | 'failed' | string
  error?: string
  request_id?: string
  results?: PlatformResult[]
}

export interface BilibiliPublishBody {
  title?: string
  description?: string
  subtitles: boolean
  title_card: boolean
  scheduled_date?: string
  timezone?: string
  visibility: 'private' | 'public'
}

export const bilibiliApi = {
  getConfig: (): Promise<BilibiliConfigView> => api.get('/publish/bilibili/config'),
  saveConfig: (body: { cookie: string }): Promise<BilibiliConfigView & { ok?: boolean }> =>
    api.put('/publish/bilibili/config', body),
  clearConfig: (): Promise<BilibiliConfigView & { ok?: boolean }> => api.delete('/publish/bilibili/config'),
  start: (projectId: string, clipId: string, body: BilibiliPublishBody): Promise<{ ok: boolean; job_id: string; status: string }> =>
    api.post(`/publish/bilibili/${projectId}/clips/${clipId}`, body),
  job: (jobId: string): Promise<BilibiliJobView> => api.get(`/publish/bilibili/jobs/${jobId}`),
}
