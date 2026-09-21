import api from '../../services/api'
import { Draft, Workspace, RenderJob, Language, CandidateList } from './types'
export const studioApi = {
  source: (pid: string) => `${api.defaults.baseURL}/studio/${pid}/source`,
  capabilities: (): Promise<{ visual_analysis: boolean; visual_model: string }> => api.get('/studio/capabilities'),
  get: (pid: string, signal?: AbortSignal): Promise<Workspace> => api.get(`/studio/${pid}`, { signal }),
  candidates: (pid: string, signal?: AbortSignal): Promise<CandidateList> => api.get(`/studio/${pid}/candidates`, { signal }),
  import: (body: FormData): Promise<{ project_id: string }> => api.post('/studio/import', body, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 0 }),
  analyze: (pid: string) => api.post(`/studio/${pid}/analyze`),
  create: (pid: string, clip_ids: string[], title: string): Promise<Draft> => api.post(`/studio/${pid}/drafts`, { clip_ids, title }),
  eventDraft: (pid: string, id: string): Promise<Draft> => api.post(`/studio/${pid}/events/${id}/draft`),
  save: (pid: string, draft: Draft): Promise<Draft> => api.put(`/studio/${pid}/drafts/${draft.id}`, draft),
  duplicate: (pid: string, draft: Draft, title: string, language: Language): Promise<Draft> => api.post(`/studio/${pid}/drafts/${draft.id}/duplicate`, { draft, title, language }),
  rewrite: (pid: string, draft: Draft, instruction: string): Promise<Draft> => api.post(`/studio/${pid}/rewrite`, { draft, instruction }, { timeout: 310000 }),
  export: (pid: string, draft: string, revision: number): Promise<RenderJob> => api.post(`/studio/${pid}/drafts/${draft}/export`, { revision }),
  video: (pid: string, jid: string, download = false) => `${api.defaults.baseURL}/studio/${pid}/exports/${jid}/video${download ? '?download=true' : ''}`,
}
export function errorText(error: unknown) {
  const detail = (error as any)?.response?.data?.detail
  return typeof detail === 'string' ? detail : (error as Error)?.message || '请求失败，请重试'
}
