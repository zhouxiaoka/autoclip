import { observeStudioOperation, studioImportProperties, studioGoals, observeStudioWorkspace } from '../../analytics/studio'
import { workflow } from '../../analytics/observer'
import api from '../../services/api'
import { Draft, Workspace, RenderJob, Language, CandidateList, ImportOptions, Goal, AnalysisMode, AnalysisPreferences } from './types'
export type SourcePreview = { status: 'idle' | 'queued' | 'running' | 'completed' | 'failed'; version?: string; error?: string }
export const studioApi = {
  preparePreview: (pid: string): Promise<SourcePreview> => api.post(`/studio/${pid}/source-preview`),
  previewStatus: (pid: string): Promise<SourcePreview> => api.get(`/studio/${pid}/source-preview`),
  compatibleSource: (pid: string, version: string) => `${api.defaults.baseURL}/studio/${pid}/source-preview/video?v=${version}`,
  analysisPreferences: (): Promise<AnalysisPreferences> => api.get('/studio/analysis-preferences'),
  saveAnalysisPreferences: (body: AnalysisPreferences): Promise<AnalysisPreferences> => observeStudioOperation('studio_analysis_preferences', () => api.put('/studio/analysis-preferences', body), undefined, { analysis_mode: body.analysis_mode, allow_visual_screening: body.allow_visual_screening }),
  source: (pid: string) => `${api.defaults.baseURL}/studio/${pid}/source`,
  capabilities: (): Promise<{ visual_analysis: boolean; visual_model: string }> => api.get('/studio/capabilities'),
  get: (pid: string, signal?: AbortSignal): Promise<Workspace> => observeStudioWorkspace(pid, () => api.get(`/studio/${pid}`, { signal })),
  titleThumbnail: (style: string, version = 6) => `${api.defaults.baseURL}/studio/title-presets/${style}/thumbnail?v=${version}`,
  titlePreview: (pid: string, draft: Draft, signal?: AbortSignal, layer = 'artwork'): Promise<Blob> => api.post(`/studio/${pid}/title-preview?layer=${layer}`, draft, {responseType:'blob', signal}),
  candidates: (pid: string, signal?: AbortSignal): Promise<CandidateList> => api.get(`/studio/${pid}/candidates`, { signal }),
  import: (body: FormData): Promise<{ project_id: string }> => observeStudioOperation('studio_import', () => api.post('/studio/import', body, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 0 }), (result: { project_id: string }) => workflow.watch('studio-screen', result.project_id, undefined, undefined, studioImportProperties(body) as Record<string, string | boolean>), studioImportProperties(body)),
  confirmPlan: (pid: string, planId: string, goals: Goal[], options: ImportOptions, analysisMode: AnalysisMode) => observeStudioOperation('studio_confirm', () => api.post(`/studio/${pid}/start`, {plan_id:planId, goals, analysis_mode:analysisMode, language:options.language, aspect:options.aspect, duration:options.duration}), () => workflow.watch('studio-production', planId, pid, undefined, { analysis_mode: analysisMode, ...studioGoals(goals) }), { analysis_mode: analysisMode, ...studioGoals(goals), aspect: options.aspect || 'auto' }),
  correctPlan: (pid: string, body: ImportOptions) => observeStudioOperation('studio_plan_update', () => api.put(`/studio/${pid}/plan`, body), () => workflow.watch('studio-screen', pid, undefined, undefined, {}, true), {goal: body.goal, aspect: body.aspect || 'auto'}),
  analyze: (pid: string) => observeStudioOperation('studio_rescreen', () => api.post(`/studio/${pid}/analyze`), () => workflow.watch('studio-screen', pid, undefined, undefined, {}, true)),
  create: (pid: string, clip_ids: string[], title: string, reuse_existing = false): Promise<Draft> => observeStudioOperation('studio_draft_create', () => api.post(`/studio/${pid}/drafts`, { clip_ids, title, reuse_existing }), undefined, {source_type: 'content_clip'}),
  eventDraft: (pid: string, id: string): Promise<Draft> => observeStudioOperation('studio_draft_create', () => api.post(`/studio/${pid}/events/${id}/draft`), undefined, {source_type: 'visual_event'}),
  save: (pid: string, draft: Draft): Promise<Draft> => observeStudioOperation('studio_draft_save', () => api.put(`/studio/${pid}/drafts/${draft.id}`, draft), undefined, { aspect: draft.aspect, subtitle_enabled: draft.subtitles, title_style: draft.title_style }),
  duplicate: (pid: string, draft: Draft, title: string, language: Language): Promise<Draft> => observeStudioOperation('studio_draft_duplicate', () => api.post(`/studio/${pid}/drafts/${draft.id}/duplicate`, { draft, title, language }), undefined, { aspect: draft.aspect, subtitle_enabled: draft.subtitles, title_style: draft.title_style }),
  rewrite: (pid: string, draft: Draft, instruction: string): Promise<Draft> => observeStudioOperation('studio_rewrite', () => api.post(`/studio/${pid}/rewrite`, { draft, instruction }, { timeout: 310000 }), undefined, { aspect: draft.aspect, subtitle_enabled: draft.subtitles, title_style: draft.title_style }),
  export: (pid: string, draft: string, revision: number, settings?: Pick<Draft, 'aspect' | 'subtitles' | 'title_style'>): Promise<RenderJob> => observeStudioOperation('studio_export', () => api.post(`/studio/${pid}/drafts/${draft}/export`, { revision }), (job: RenderJob) => workflow.watch('studio-export', job.job_id, pid, undefined, { aspect: settings?.aspect, subtitle_enabled: settings?.subtitles, title_style: settings?.title_style }), { aspect: settings?.aspect, subtitle_enabled: settings?.subtitles, title_style: settings?.title_style }),
  thumbnail: (pid: string, draft: string, revision: number, job?: string) => `${api.defaults.baseURL}/studio/${pid}/drafts/${draft}/thumbnail?revision=${revision}${job ? `&job_id=${job}` : ''}`,
  video: (pid: string, jid: string, download = false) => `${api.defaults.baseURL}/studio/${pid}/exports/${jid}/video${download ? '?download=true' : ''}`,
}
export function errorText(error: unknown) {
  const detail = (error as any)?.response?.data?.detail
  return typeof detail === 'string' ? detail : (error as Error)?.message || '请求失败，请重试'
}
