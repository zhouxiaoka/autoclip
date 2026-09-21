import api from '../../services/api'
import { Draft, Workspace, RenderJob } from './types'
export const studioApi = {
  source: (pid: string) => `${api.defaults.baseURL}/studio/${pid}/source`,
  capabilities: (): Promise<{ visual_analysis: boolean; visual_model: string }> => api.get('/studio/capabilities'),
  get: (pid: string, signal?: AbortSignal): Promise<Workspace> => api.get(`/studio/${pid}`, { signal }),
  import: (body: FormData): Promise<{ project_id: string }> => api.post('/studio/import', body, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 0 }),
  analyze: (pid: string) => api.post(`/studio/${pid}/analyze`),
  create: (pid: string, clip_ids: string[], title: string): Promise<Draft> => api.post(`/studio/${pid}/drafts`, { clip_ids, title }),
  eventDraft: (pid: string, id: string): Promise<Draft> => api.post(`/studio/${pid}/events/${id}/draft`),
  save: (pid: string, draft: Draft): Promise<Draft> => api.put(`/studio/${pid}/drafts/${draft.id}`, draft),
  rewrite: (pid: string, draft: Draft, instruction: string): Promise<Draft> => api.post(`/studio/${pid}/rewrite`, { draft, instruction }, { timeout: 180000 }),
  export: (pid: string, draft: string): Promise<RenderJob> => api.post(`/studio/${pid}/drafts/${draft}/export`),
  video: (pid: string, jid: string, download = false) => `${api.defaults.baseURL}/studio/${pid}/exports/${jid}/video${download ? '?download=true' : ''}`,
}
export function errorText(error: unknown) {
  const detail = (error as any)?.response?.data?.detail
  return typeof detail === 'string' ? detail : (error as Error)?.message || '请求失败，请重试'
}
