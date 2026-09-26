import { observeStudioOperation } from '../../analytics/studio'
import { workflow } from '../../analytics/observer'
import api from '../../services/api'
import { Draft, Workspace, RenderJob, Language, CandidateList, ImportOptions, Goal, AnalysisMode, AnalysisPreferences } from './types'
export const studioApi = {
  analysisPreferences: (): Promise<AnalysisPreferences> => api.get('/studio/analysis-preferences'),
  saveAnalysisPreferences: (body: AnalysisPreferences): Promise<AnalysisPreferences> => api.put('/studio/analysis-preferences', body),
  source: (pid: string) => `${api.defaults.baseURL}/studio/${pid}/source`,
  capabilities: (): Promise<{ visual_analysis: boolean; visual_model: string }> => api.get('/studio/capabilities'),
  get: (pid: string, signal?: AbortSignal): Promise<Workspace> => api.get(`/studio/${pid}`, { signal }),
  titleThumbnail: (style: string, version = 6) => `${api.defaults.baseURL}/studio/title-presets/${style}/thumbnail?v=${version}`,
  titlePreview: (pid: string, draft: Draft, signal?: AbortSignal, layer = 'artwork'): Promise<Blob> => api.post(`/studio/${pid}/title-preview?layer=${layer}`, draft, {responseType:'blob', signal}),
  candidates: (pid: string, signal?: AbortSignal): Promise<CandidateList> => api.get(`/studio/${pid}/candidates`, { signal }),
  import: (body: FormData): Promise<{ project_id: string }> => observeStudioOperation('studio_import', () => api.post('/studio/import', body, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 0 }), (result: { project_id: string }) => workflow.watch('studio-screen', result.project_id)),
  confirmPlan: (pid: string, planId: string, goals: Goal[], options: ImportOptions, analysisMode: AnalysisMode) => observeStudioOperation('studio_confirm', () => api.post(`/studio/${pid}/start`, {plan_id:planId, goals, analysis_mode:analysisMode, language:options.language, aspect:options.aspect, duration:options.duration}), () => workflow.watch('studio-production', planId, pid)),
  correctPlan: (pid: string, body: ImportOptions) => api.put(`/studio/${pid}/plan`, body),
  analyze: (pid: string) => api.post(`/studio/${pid}/analyze`),
  create: (pid: string, clip_ids: string[], title: string, reuse_existing = false): Promise<Draft> => api.post(`/studio/${pid}/drafts`, { clip_ids, title, reuse_existing }),
  eventDraft: (pid: string, id: string): Promise<Draft> => api.post(`/studio/${pid}/events/${id}/draft`),
  save: (pid: string, draft: Draft): Promise<Draft> => api.put(`/studio/${pid}/drafts/${draft.id}`, draft),
  duplicate: (pid: string, draft: Draft, title: string, language: Language): Promise<Draft> => api.post(`/studio/${pid}/drafts/${draft.id}/duplicate`, { draft, title, language }),
  rewrite: (pid: string, draft: Draft, instruction: string): Promise<Draft> => api.post(`/studio/${pid}/rewrite`, { draft, instruction }, { timeout: 310000 }),
  export: (pid: string, draft: string, revision: number): Promise<RenderJob> => observeStudioOperation('studio_export', () => api.post(`/studio/${pid}/drafts/${draft}/export`, { revision }), (job: RenderJob) => workflow.watch('studio-export', job.job_id, pid)),
  thumbnail: (pid: string, draft: string, revision: number, job?: string) => `${api.defaults.baseURL}/studio/${pid}/drafts/${draft}/thumbnail?revision=${revision}${job ? `&job_id=${job}` : ''}`,
  video: (pid: string, jid: string, download = false) => `${api.defaults.baseURL}/studio/${pid}/exports/${jid}/video${download ? '?download=true' : ''}`,
}
export function errorText(error: unknown) {
  const detail = (error as any)?.response?.data?.detail
  return typeof detail === 'string' ? detail : (error as Error)?.message || '请求失败，请重试'
}
