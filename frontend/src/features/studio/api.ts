import { captureBusinessEvent } from '../../analytics/posthog'
import { safeStudioProperties, telemetryId, type AttemptReceipt, type Properties } from '../../analytics/workflow'
import { observeStudioOperation, studioImportProperties, studioGoals, observeStudioWorkspace } from '../../analytics/studio'
import { workflow } from '../../analytics/observer'
import api from '../../services/api'
import type { ImportReadiness } from './importReadiness'
import { probeConfig } from './transcriptionRecovery'
import { Draft, Workspace, RenderJob, Language, CandidateList, ImportOptions, Goal, AnalysisMode, AnalysisPreferences, SubtitleCue, FramingStatus, AutoFrameResult, PlatformStrategySummary, OutputVariant, PostCopy } from './types'
import { noteWorkspaceCompletion } from './noticeRuntime'
import { effectiveSubtitles } from './subtitleState'
export type SourcePreview = { status: 'idle' | 'queued' | 'running' | 'completed' | 'failed'; version?: string; error?: string }
export function draftProperties(draft?: Partial<Draft>): Properties {
  const packaging = draft?.packaging
  return safeStudioProperties({ aspect: draft?.aspect, subtitle_enabled: draft ? effectiveSubtitles(draft) : undefined, title_style: draft?.title_style,
    layout: draft?.layout, has_crop_track: !!draft?.scenes?.some(s => s.crop_track?.length),
    has_manual_adjustment: !!draft?.scenes?.some(s => s.framing_adjusted),
    auto_frame_retained: (draft?.layout === 'crop' || draft?.layout === 'window') && !!draft?.scenes?.some(s => s.framing_source === 'auto' && !s.framing_adjusted && s.crop_track?.length),
    // Template packaging: enums and booleans only, never the title, captions, names or tags.
    template: packaging?.template, packaging_style: packaging ? packaging.style || (packaging.template === 'podcast_en' ? 'pop' : 'classic') : undefined,
    tags_enabled: packaging ? packaging.tags_enabled : undefined, packaging_fallback: packaging ? packaging.fallback : undefined,
  })
}
type RetryReceipt = { attempt?: AttemptReceipt | null }
/** One key per click: the same request re-sent returns the same receipt (backend idempotency). */
const retryKey = () => `r-${telemetryId()}`

export const studioApi = {
  preparePreview: (pid: string): Promise<SourcePreview> => api.post(`/studio/${pid}/source-preview`),
  previewStatus: (pid: string): Promise<SourcePreview> => api.get(`/studio/${pid}/source-preview`),
  compatibleSource: (pid: string, version: string) => `${api.defaults.baseURL}/studio/${pid}/source-preview/video?v=${version}`,
  analysisPreferences: (): Promise<AnalysisPreferences> => api.get('/studio/analysis-preferences'),
  saveAnalysisPreferences: (body: AnalysisPreferences): Promise<AnalysisPreferences> => observeStudioOperation('studio_analysis_preferences', () => api.put('/studio/analysis-preferences', body), undefined, { analysis_mode: body.analysis_mode, allow_visual_screening: body.allow_visual_screening }),
  source: (pid: string) => `${api.defaults.baseURL}/studio/${pid}/source`,
  subtitles: (pid: string, signal?: AbortSignal): Promise<{ cues: SubtitleCue[] }> => api.get(`/studio/${pid}/subtitles`, { signal }),
  framingStatus: (): Promise<FramingStatus> => api.get('/studio/framing/status'),
  framingInstall: (): Promise<FramingStatus & { started: boolean }> => observeStudioOperation('studio_framing_install', () => api.post('/studio/framing/install'), (_result, props) => workflow.watch('framing-runtime', 'runtime', undefined, undefined, props, true)),
  autoFrame: (pid: string, draft: Draft, trigger: 'auto' | 'manual' | 'portrait_preset' = 'manual'): Promise<AutoFrameResult> => observeStudioOperation('studio_auto_frame', () => api.post(`/studio/${pid}/auto-frame`, draft, { timeout: 120000 }), (result: AutoFrameResult, props) => {
    const framed = result.scenes.filter(s => s.crop_x !== null).length
    captureBusinessEvent('studio_auto_frame_finished', safeStudioProperties({ ...props, outcome: 'completed', framing_outcome: framed ? 'framed' : 'no_detection', framed_count: framed, scene_count: result.scenes.length, fit_count: result.scenes.reduce((n,s) => n + s.fit_shots, 0) }))
  }, { ...workflow.context(pid), trigger, ...draftProperties(draft) }),
  readiness: (): Promise<ImportReadiness> => api.get('/studio/readiness'),
  /* the install-recovery probe (probeConfig: one attempt, READINESS_TIMEOUT_MS, the round's
signal); every HTTP answer (even a 500) is seen. */
  readinessProbe: (signal: AbortSignal): Promise<ImportReadiness> => api.get('/studio/readiness', probeConfig(signal)),
  capabilities: (): Promise<{ visual_analysis: boolean; visual_model: string }> => api.get('/studio/capabilities'),
  platformStrategies: (): Promise<{ strategies: PlatformStrategySummary[] }> => api.get('/studio/platform-strategies'),
  retryOutputVariant: (pid: string, variantId: string): Promise<OutputVariant> =>
    // #419: the one retry command. The backend validates the parent and returns the attempt receipt;
    // retry_of / attempt_id come from it, never from local watches.
    observeStudioOperation('studio_variant_retry', () => api.post<unknown, RetryReceipt & { variant: OutputVariant }>(`/studio/${pid}/retry`, { scope: 'variant', variant_id: variantId, idempotency_key: retryKey() }), (result, props) => {
      const link = result.attempt?.retry_of ? { retry_of: result.attempt.retry_of } : {}
      workflow.watch('studio-variant', variantId, pid, undefined, { ...props, ...link }, true, result.variant.render_job_id || result.variant.render_attempt_id || result.variant.preparation_run_id)
      workflow.watchAttempt(pid, result.attempt, props)
    }, workflow.context(pid)).then(result => result.variant),
  variantCover: (pid: string, variantId: string, stamp = 0) => `${api.defaults.baseURL}/studio/${pid}/output-variants/${variantId}/cover?t=${stamp}`,
  variantKit: (pid: string, variantId: string) => `${api.defaults.baseURL}/studio/${pid}/output-variants/${variantId}/kit`,
  updateVariantPost: (pid: string, variantId: string, post: PostCopy): Promise<PostCopy> => observeStudioOperation('studio_post_save', () => api.put(`/studio/${pid}/output-variants/${variantId}/post`, post), undefined, workflow.context(pid)),
  redesignVariantCover: (pid: string, variantId: string): Promise<NonNullable<OutputVariant['cover_job']>> => observeStudioOperation('studio_cover_redesign', () => api.post(`/studio/${pid}/output-variants/${variantId}/cover/ai`), (job: NonNullable<OutputVariant['cover_job']>, props) => {
    workflow.watch('studio-cover', job.job_id, pid, undefined, props)
    for (const watch of workflow.list().filter(w => w.kind === 'studio-cover' && w.projectId === pid && w.id === job.job_id)) workflow.observeCoverJob(watch, job)
  }, workflow.context(pid)),
  variantCoverJob: async (pid: string, variantId: string): Promise<NonNullable<OutputVariant['cover_job']>> => {
    const generation = workflow.generation(), enabled = workflow.active(generation)
    const job = await api.get<unknown, NonNullable<OutputVariant['cover_job']>>(`/studio/${pid}/output-variants/${variantId}/cover/ai`)
    // Observe the result already polled by the UI before another redesign overwrites it.
    if (enabled && workflow.active(generation)) {
      for (const watch of workflow.list().filter(w => w.kind === 'studio-cover' && w.projectId === pid && w.id === job.job_id)) workflow.observeCoverJob(watch, job)
    }
    return job
  },
  produceOutputVariant: (pid: string, variantId: string, strategyId: string): Promise<OutputVariant> => observeStudioOperation('studio_variant_produce', () => api.post(`/studio/${pid}/output-variants/${variantId}/produce`), (variant: OutputVariant, props) => workflow.watch('studio-variant', variantId, pid, undefined, props, false, variant.render_job_id), { ...workflow.context(pid), strategy_id: strategyId }),
  get: async (pid: string, signal?: AbortSignal): Promise<Workspace> => {
    const snapshot = await observeStudioWorkspace(pid, () => api.get(`/studio/${pid}`, { signal }) as Promise<Workspace>)
    noteWorkspaceCompletion(pid, snapshot)
    return snapshot
  },
  titleThumbnail: (style: string, version = 6) => `${api.defaults.baseURL}/studio/title-presets/${style}/thumbnail?v=${version}`,
  titlePreview: (pid: string, draft: Draft, signal?: AbortSignal, layer = 'artwork'): Promise<Blob> => api.post(`/studio/${pid}/title-preview?layer=${layer}`, draft, {responseType:'blob', signal}),
  candidates: (pid: string, signal?: AbortSignal): Promise<CandidateList> => api.get(`/studio/${pid}/candidates`, { signal }),
  import: (body: FormData): Promise<{ project_id: string; analysis_run_id?: string }> => {
    const props = studioImportProperties(body)
    return observeStudioOperation('studio_import', () => api.post('/studio/import', body, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 0 }), (result: { project_id: string; analysis_run_id?: string }, observed) => {
      workflow.rememberProject(result.project_id, props)
      workflow.watch('studio-screen', result.project_id, undefined, undefined, observed, false, result.analysis_run_id)
      // Automatic output has no confirmation step: watch the generation itself to its terminal state.
      if (body.get?.('auto_start') === 'true') workflow.watch('studio-generation', result.project_id, undefined, undefined, observed, false, result.analysis_run_id)
    }, props)
  },
  confirmPlan: (pid: string, planId: string, goals: Goal[], options: ImportOptions, analysisMode: AnalysisMode) => observeStudioOperation('studio_confirm', () => api.post<unknown, { analysis_run_id?: string }>(`/studio/${pid}/start`, {plan_id:planId, goals, analysis_mode:analysisMode, language:options.language, aspect:options.aspect, duration:options.duration}), (_result, props) => workflow.watch('studio-production', planId, pid, undefined, { ...props, ...workflow.context(pid), analysis_mode: analysisMode, ...studioGoals(goals) }, false, _result.analysis_run_id), { ...workflow.context(pid), analysis_mode: analysisMode, ...studioGoals(goals), aspect: options.aspect || 'auto' }),
  correctPlan: (pid: string, body: ImportOptions) => observeStudioOperation('studio_plan_update', () => api.put<unknown, { analysis_run_id?: string }>(`/studio/${pid}/plan`, body), (_result, props) => workflow.watch('studio-screen', pid, undefined, undefined, props, true, _result.analysis_run_id), {...workflow.context(pid), goal: body.goal, aspect: body.aspect || 'auto'}),
  analyze: (pid: string, automatic = false) => observeStudioOperation('studio_rescreen', () => api.post<unknown, { analysis_run_id?: string }>(`/studio/${pid}/analyze`), (_result, props) => {
    workflow.watch('studio-screen', pid, undefined, undefined, props, true, _result.analysis_run_id)
    if (automatic) workflow.watch('studio-generation', pid, undefined, undefined, props, false, _result.analysis_run_id)
  }, workflow.context(pid)),
  /** The failed-state 「重试」/「继续制作」 (#419): one backend retry command; the receipt carries retry_of. A manual
   * project's production attempt is opened now and bound when the plan is confirmed. */
  retry: (pid: string) => observeStudioOperation('studio_rescreen', () => api.post<unknown, RetryReceipt & { analysis_run_id?: string }>(`/studio/${pid}/retry`, { scope: 'analysis', idempotency_key: retryKey() }), (result, props) => {
    const link = result.attempt?.retry_of ? { retry_of: result.attempt.retry_of } : {}
    workflow.watch('studio-screen', pid, undefined, undefined, { ...props, ...link }, true, result.analysis_run_id)
    if (result.attempt?.kind === 'generation') workflow.watchAttempt(pid, result.attempt, props)
  }, workflow.context(pid)),
  create: (pid: string, clip_ids: string[], title: string, reuse_existing = false): Promise<Draft> => observeStudioOperation('studio_draft_create', () => api.post(`/studio/${pid}/drafts`, { clip_ids, title, reuse_existing }), undefined, {...workflow.context(pid), source_type: 'content_clip'}),
  eventDraft: (pid: string, id: string): Promise<Draft> => observeStudioOperation('studio_draft_create', () => api.post(`/studio/${pid}/events/${id}/draft`), undefined, {...workflow.context(pid), source_type: 'visual_event'}),
  save: (pid: string, draft: Draft): Promise<Draft> => observeStudioOperation('studio_draft_save', () => api.put(`/studio/${pid}/drafts/${draft.id}`, draft), undefined, { ...workflow.context(pid), ...draftProperties(draft) }),
  duplicate: (pid: string, draft: Draft, title: string, language: Language): Promise<Draft> => observeStudioOperation('studio_draft_duplicate', () => api.post(`/studio/${pid}/drafts/${draft.id}/duplicate`, { draft, title, language }), undefined, { ...workflow.context(pid), ...draftProperties(draft) }),
  rewrite: (pid: string, draft: Draft, instruction: string): Promise<Draft> => observeStudioOperation('studio_rewrite', () => api.post(`/studio/${pid}/rewrite`, { draft, instruction }, { timeout: 310000 }), undefined, { ...workflow.context(pid), ...draftProperties(draft) }),
  export: (pid: string, draft: string, revision: number, settings?: Partial<Draft>, variantId?: string): Promise<RenderJob> => observeStudioOperation('studio_export', () => api.post(`/studio/${pid}/drafts/${draft}/export`, { revision, ...(variantId ? { variant_id: variantId } : {}) }), (job: RenderJob, props) => workflow.watch('studio-export', job.job_id, pid, undefined, { ...props, ...workflow.context(pid, job.job_id) }), { ...workflow.context(pid), ...draftProperties(settings) }),
  thumbnail: (pid: string, draft: string, revision: number, job?: string) => `${api.defaults.baseURL}/studio/${pid}/drafts/${draft}/thumbnail?revision=${revision}${job ? `&job_id=${job}` : ''}`,
  video: (pid: string, jid: string, download = false) => `${api.defaults.baseURL}/studio/${pid}/exports/${jid}/video${download ? '?download=true' : ''}`,
}
export { errorText, errorCode } from './errorText'
