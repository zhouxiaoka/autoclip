/** Versioned business telemetry. Only explicit UI operations enroll projects. */
export type Properties = Record<string, string | number | boolean | null | undefined>
export type Watch = { kind: 'project' | 'export' | 'bilibili' | 'youtube' | 'studio-screen' | 'studio-production' | 'studio-export' | 'studio-generation' | 'studio-cover' | 'studio-variant' | 'framing-runtime'; id: string; projectId?: string; since: number; seen: string[]; settled?: boolean; properties?: Properties; token?: string; runId?: string }
export const WORKFLOW_KEY = 'autoclip.analytics.workflow.v2'
const TTL = 7 * 86400000
const LIMIT = 50
const CONTEXT_KEY = "autoclip.analytics.context.v1"
export function telemetryId(): string { return `t-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}` }
type Context = { props: Properties; updated: number; artifacts: Record<string, string> }

export function projectProperties(project: { settings?: Record<string, unknown>; processing_config?: Record<string, unknown>; material_origin?: unknown; example_version?: unknown }): Properties {
  const settings = project.processing_config || project.settings
  const origin = project.material_origin || (settings ? settings.example === true ? 'sample' : 'user' : 'unknown')
  return safeStudioProperties({ material_origin: origin, example_version: project.example_version || settings?.example_version })
}

/** Explicit property contract: never spread user/model data into a payload. */
export function safeStudioProperties(value: Record<string, unknown> | null = {}): Properties {
  const input = value && typeof value === 'object' ? value : {}
  const out: Properties = { studio_schema_version: 2 }
  const enums: Record<string, string[]> = {
    strategy_id: ['douyin', 'tiktok', 'instagram_reels', 'youtube_shorts', 'youtube_long', 'bilibili', 'xiaohongshu', 'original'],
    material_origin: ['sample', 'user', 'unknown'], layout: ['crop', 'fit', 'blur', 'window'],
    generation_reason: ['content_complete', 'platform_append', 'platform_ineligible'],
    trigger: ['auto', 'manual', 'portrait_preset'], framing_outcome: ['framed', 'no_detection'],
    framing_status: ['installed', 'installing', 'failed', 'missing', 'not_installed', 'error'],
    source_type: ['file', 'youtube', 'bilibili', 'other_url', 'visual_event', 'content_clip', 'studio', 'legacy'],
    analysis_mode: ['subtitle', 'visual', 'auto'], goal: ['content', 'highlight', 'promo', 'auto'],
    aspect: ['original', 'portrait', 'landscape', 'auto'],
    portrait_style: ['auto', 'interview', 'podcast'], artifact_type: ['video', 'publish_kit'],
    recommendation_mode: ['ai', 'local', 'manual', 'fallback'],
    subtitle_status: ['available', 'missing', 'invalid', 'unreadable', 'too_large'],
    outcome: ['completed', 'failed', 'partial', 'recommended', 'manual', 'fallback', 'scheduled', 'inbox', 'unknown', 'auto_started'],
    download_mode: ['native', 'browser'], gateway: ['bilibili', 'upload-post'],
    title_style: ['plain', 'impact', 'card', 'comic', 'neon', 'arena', 'editorial', 'pixel', 'frosted'],
    share_target: ['copy_caption', 'use_case_discussion'],
    output_rating: ['ready', 'needs_edit', 'unusable'],
    template: ['interview_zh', 'podcast_en', 'landscape', 'none'],
    packaging_style: ['classic', 'boxed', 'spotlight', 'pop', 'cinematic'],
    framing: ['speaker', 'full_frame', 'full_frame_pending', 'full_frame_captions'],
  }
  for (const [key, allowed] of Object.entries(enums)) {
    if (typeof input[key] === 'string' && allowed.includes(input[key] as string)) out[key] = input[key] as string
  }
  for (const key of ['outro_applied', 'brand_outro_enabled', 'reused_content_profile', 'has_crop_track', 'has_manual_adjustment', 'auto_frame_retained', 'tags_enabled', 'packaging_fallback', 'burned_captions', 'subtitle_enabled', 'has_subtitle', 'goal_content', 'goal_highlight', 'goal_promo', 'allow_visual_screening', 'scheduled', ...['requested', 'succeeded', 'failed'].flatMap(p => ['content', 'highlight', 'promo'].map(g => `${p}_${g}`))]) {
    if (typeof input[key] === 'boolean') out[key] = input[key] as boolean
  }
  for (const key of ['warning_count', 'outro_applied_count', 'outro_fallback_count', 'outro_unknown_count', 'full_frame_count', 'framing_pending_count', 'framing_captions_count', 'example_version', 'framed_count', 'scene_count', 'fit_count', 'duration_ms', 'request_duration_ms', 'variant_count', 'completed_variant_count', 'failed_variant_count', 'skipped_variant_count', 'on_demand_variant_count', 'interview_count', 'podcast_count', 'landscape_count', 'speaker_framed_count', 'packaging_fallback_count', 'trimmed_count', 'platform_count', 'result_count', 'requested_count', 'succeeded_count', 'failed_count']) {
    if (typeof input[key] === 'number' && Number.isFinite(input[key]) && (input[key] as number) >= 0) out[key] = input[key] as number
  }
  for (const prefix of ['requested', 'succeeded', 'failed']) {
    const goals = input[`${prefix}_goals`]
    if (Array.isArray(goals)) {
      const valid = ['content', 'highlight', 'promo'].filter(g => goals.includes(g))
      out[`${prefix}_count`] = valid.length
      for (const goal of ['content', 'highlight', 'promo']) out[`${prefix}_${goal}`] = valid.includes(goal)
    }
  }
  if (typeof input.error_code === 'string' && /^(http_[45][0-9]{2}|network|timeout|unknown|validation|missing_resource|unexpected|connection|authentication|rate_limited|provider_error|invalid_response|output_truncated|refused|multiple|llm_not_configured|whisper_not_installed|whisper_install_failed|transcription_empty|subtitle_setup|timeline_empty)$/.test(input.error_code)) out.error_code = input.error_code
  for (const key of ['flow_id', 'operation_id', 'artifact_id', 'attempt_id']) {
    if (typeof input[key] === 'string' && /^t-[a-z0-9-]{10,100}$/.test(input[key] as string)) out[key] = input[key] as string
  }
  return out
}

export function errorCode(error: unknown): string {
  const e = error as { code?: string; response?: { status?: number } } | undefined
  const status = e?.response?.status
  if (typeof status === 'number' && Number.isInteger(status) && status >= 400 && status <= 599) return `http_${status}`
  if (e?.code === 'ECONNABORTED' || e?.code === 'ETIMEDOUT') return 'timeout'
  if (e?.code === 'ERR_NETWORK') return 'network'
  return 'unknown'
}

export function utcMillis(value?: string | null): number | undefined {
  if (!value) return undefined
  const n = Date.parse(/Z$|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
  return Number.isFinite(n) ? n : undefined
}

export function routeName(path: string): string {
  const p = path.split(/[?#]/)[0]
  if (/^\/project\/[^/]+\/publish(?:\/[^/]+)?\/?$/.test(p)) return '/project/:id/publish/:clipId'
  if (/^\/import\/[^/]+\/?$/.test(p)) return '/import/:id'
  if (/^\/project\/[^/]+\/studio\/[^/]+\/?$/.test(p)) return '/project/:id/studio/:draftId'
  if (/^\/project\/[^/]+\/?$/.test(p)) return '/project/:id'
  return ['/', '/settings'].includes(p) ? p : '/other'
}

export interface TaskSnapshot {
  id: string; task_type: string; status: string; created_at: string
  started_at?: string | null; completed_at?: string | null
}

export interface StudioSnapshot {
  material_origin?: 'sample' | 'user' | 'unknown'
  example_version?: number
  analysis_history?: { run_id: string; plan?: StudioSnapshot['plan']; analysis: StudioSnapshot['analysis'] }[]
  plan?: { id: string; mode?: string; confirmed_analysis?: string; recommended_analysis?: string; local_evidence?: { subtitle_status?: string } }
  analysis?: { run_id?: string; phase?: string; status: string; outcome?: string; duration_ms?: number; error_code?: string; requested_goals?: string[]; succeeded_goals?: string[]; failed_goals?: string[]; result_count?: number } | null
  jobs?: { job_id: string; status: string; duration_ms?: number; error_code?: string; brand_outro?: boolean; result?: { outro_applied?: boolean; warnings?: string[] } }[]
  generation?: { auto_start?: boolean; status?: string; error_code?: string; portrait_style?: string; branding?: { outro_enabled?: boolean }; requested_platforms?: string[]; completed_variant_count?: number; skipped?: unknown[]; source_has_burned_subtitles?: boolean; created_at?: string; finished_at?: string } | null
  output_variants?: { id?: string; draft_id: string; render_job_id?: string; strategy_id: string; status: string; framing?: string; branding?: { outro_enabled?: boolean }; trimmed_to_sec?: number; cover_job?: { job_id: string; status: string } | null }[]
  drafts?: { id: string; packaging?: { template?: string; fallback?: boolean } | null }[]
}

/** Aggregate counts for one automatic generation; no titles, captions, names or IDs. */
export function generationSummary(snapshot: StudioSnapshot): Record<string, unknown> {
  const all = snapshot.output_variants || []
  // Backup clips are not packaged until someone asks for them: template counts cover produced versions.
  const variants = all.filter(v => v.status !== 'on_demand')
  const templates = new Map((snapshot.drafts || []).map(d => [d.id, d.packaging] as const))
  const packaged = variants.map(v => templates.get(v.draft_id)).filter(Boolean)
  const count = (test: (v: (typeof variants)[number]) => boolean) => variants.filter(test).length
  const jobs = new Map((snapshot.jobs || []).map(j => [j.job_id, j]))
  const completed = variants.filter(v => v.status === 'completed').map(v => ({ variant: v, job: jobs.get(v.render_job_id || '') }))
  const created = utcMillis(snapshot.generation?.created_at), finished = utcMillis(snapshot.generation?.finished_at)
  return {
    variant_count: all.length,
    completed_variant_count: count(v => v.status === 'completed'),
    failed_variant_count: count(v => v.status === 'failed'),
    on_demand_variant_count: all.length - variants.length,
    skipped_variant_count: Array.isArray(snapshot.generation?.skipped) ? snapshot.generation!.skipped!.length : 0,
    platform_count: snapshot.generation?.requested_platforms?.length || 0,
    interview_count: packaged.filter(p => p?.template === 'interview_zh').length,
    podcast_count: packaged.filter(p => p?.template === 'podcast_en').length,
    landscape_count: variants.length - packaged.length,
    speaker_framed_count: count(v => v.framing === 'speaker'),
    full_frame_count: count(v => v.framing === 'full_frame'),
    framing_pending_count: count(v => v.framing === 'full_frame_pending'),
    framing_captions_count: count(v => v.framing === 'full_frame_captions'),
    portrait_style: snapshot.generation?.portrait_style,
    brand_outro_enabled: snapshot.generation?.branding?.outro_enabled,
    outro_applied_count: completed.filter(({ job }) => job?.result?.outro_applied === true).length,
    outro_fallback_count: completed.filter(({ variant, job }) => (job?.brand_outro ?? variant.branding?.outro_enabled) === true && job?.result?.outro_applied === false).length,
    outro_unknown_count: completed.filter(({ job }) => typeof job?.result?.outro_applied !== 'boolean').length,
    packaging_fallback_count: packaged.filter(p => p?.fallback).length,
    trimmed_count: count(v => !!v.trimmed_to_sec),
    burned_captions: !!snapshot.generation?.source_has_burned_subtitles,
    duration_ms: created !== undefined && finished !== undefined ? Math.max(0, finished - created) : undefined,
  }
}

/** Storage and capture are injected so offline/privacy/replay behavior is testable. */
export class WorkflowTracker {
  private watches: Watch[] = []
  private epoch = 0
  private contexts: Record<string, Context> = {}
  constructor(
    private storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>,
    private enabled: () => boolean,
    private capture: (event: string, properties: Properties) => boolean,
    private now: () => number = Date.now,
  ) {
    try {
      const raw: unknown = JSON.parse(storage.getItem(WORKFLOW_KEY) || '[]')
      if (Array.isArray(raw)) this.watches = raw.filter((w): w is Watch =>
        w && ['project', 'export', 'bilibili', 'youtube', 'studio-screen', 'studio-production', 'studio-export', 'studio-generation', 'studio-cover', 'studio-variant', 'framing-runtime'].includes(w.kind) &&
        typeof w.id === 'string' && Number.isFinite(w.since) && Array.isArray(w.seen) &&
        w.seen.every((v: unknown) => typeof v === 'string') && w.seen.length <= 2000 &&
        (w.projectId === undefined || typeof w.projectId === 'string') &&
        (w.runId === undefined || typeof w.runId === 'string'))
    } catch { /* corrupted/unavailable storage cannot block the application */ }
    try {
      const raw = JSON.parse(storage.getItem(CONTEXT_KEY) || '{}')
      for (const [key, value] of Object.entries(raw).slice(-500)) {
        const c = value as Context
        if (c && Number.isFinite(c.updated) && c.updated > this.now() - 35 * 86400000) {
          this.contexts[key] = { props: safeStudioProperties(c.props), updated: c.updated, artifacts: Object.fromEntries(Object.entries(c.artifacts || {}).filter(([,v]) => typeof v === 'string' && /^t-[a-z0-9-]{10,100}$/.test(v)).slice(-100)) }
        }
      }
    } catch { /* unavailable storage */ }
    if (!this.enabled()) this.clear()
    this.prune()
  }
  private persistContexts(): void {
    const entries = Object.entries(this.contexts).filter(([,c]) => c.updated > this.now() - 35 * 86400000).sort((a,b) => a[1].updated - b[1].updated).slice(-500)
    this.contexts = Object.fromEntries(entries)
    try { this.storage.setItem(CONTEXT_KEY, JSON.stringify(this.contexts)) } catch { /* best effort */ }
  }
  rememberProject(id: string, input: Record<string, unknown>): void {
    if (!this.enabled() || !id) return
    const before = this.contexts[id]
    const props = safeStudioProperties(input)
    this.contexts[id] = { props: { ...before?.props, ...props, flow_id: before?.props.flow_id || props.flow_id || telemetryId() }, updated: this.now(), artifacts: before?.artifacts || {} }
    this.persistContexts()
  }
  context(id?: string, artifact?: string): Properties {
    if (!this.enabled() || !id) return { material_origin: 'unknown' }
    if (!this.contexts[id]) this.rememberProject(id, { material_origin: 'unknown' })
    const c = this.contexts[id]
    if (artifact && !c.artifacts[artifact]) {
      c.artifacts[artifact] = telemetryId()
      c.artifacts = Object.fromEntries(Object.entries(c.artifacts).slice(-100))
      this.persistContexts()
    }
    return { flow_id: c.props.flow_id, material_origin: c.props.material_origin || 'unknown', ...(c.props.example_version !== undefined ? { example_version: c.props.example_version } : {}), ...(artifact ? { artifact_id: c.artifacts[artifact] } : {}) }
  }
  private prune(): void {
    this.watches = this.watches.filter(w => w.since > this.now() - TTL && w.since <= this.now()).slice(-LIMIT)
  }
  private persist(): void {
    try { this.storage.setItem(WORKFLOW_KEY, JSON.stringify(this.watches)) } catch { /* best effort */ }
  }
  clear(): void {
    this.epoch++
    this.watches = []
    this.contexts = {}
    try { this.storage.removeItem(CONTEXT_KEY) } catch { /* best effort */ }
    try { this.storage.removeItem(WORKFLOW_KEY) } catch { /* best effort */ }
  }
  generation(): number { return this.epoch }
  active(generation: number): boolean { return generation === this.epoch && this.enabled() }
  list(): Watch[] {
    if (!this.enabled()) { this.clear(); return [] }
    this.prune()
    return [...this.watches]
  }
  watch(kind: Watch['kind'], id: string, projectId?: string, since = this.now(), properties: Properties = {}, restart = false, runId?: string): void {
    if (!this.enabled() || !id) return
    this.prune()
    const existing = this.watches.find(w => w.kind === kind && w.id === id && (!runId || w.runId === runId))
    if (existing && (!existing.settled || kind === 'studio-export') && !restart) return
    if (existing) this.watches = this.watches.filter(w => w !== existing)
    this.watches.push({ kind, id, runId, projectId, since, seen: [], properties: safeStudioProperties({ ...this.context(projectId || id), ...properties }), token: telemetryId() })
    this.prune()
    this.persist()
  }
  emitOnce(w: Watch, key: string, event: string, properties: Properties): void {
    if (!this.enabled() || !this.watches.includes(w) || w.seen.includes(key) || w.seen.length >= 2000) return
    if (this.capture(event, (w.kind.startsWith('studio-') || w.kind === 'framing-runtime') ? { ...safeStudioProperties(w.properties), ...safeStudioProperties(properties), ...safeStudioProperties({ attempt_id: w.token }), ...(w.token && /^[a-z0-9-]{10,100}$/.test(w.token) ? { $insert_id: `studio-v1:${w.token}:${key}` } : {}) } : { ...this.context(w.projectId || w.id), ...properties, $insert_id: `autoclip-v2:${w.kind}:${w.id}:${key}` })) {
      w.seen.push(key)
      this.persist()
    }
  }
  observeCoverJob(w: Watch, job?: { job_id: string; status: string } | null): void {
    if (w.kind !== 'studio-cover' || w.settled || job?.job_id !== w.id || !['completed', 'failed'].includes(job.status)) return
    this.emitOnce(w, 'finished', 'studio_cover_redesign_finished', safeStudioProperties({ ...this.context(w.projectId), outcome: job.status }))
    if (w.seen.includes('finished')) { w.settled = true; this.persist() }
  }
  /** IDs remain in local watches only; external payload follows the versioned aggregate contract. */
  observeStudio(w: Watch, snapshot: StudioSnapshot): void {
    if (w.settled) return
    const original = snapshot
    if (w.runId && w.kind !== 'studio-variant') {
      const receipt = snapshot.analysis_history?.find(r => r.run_id === w.runId)
      if (receipt) snapshot = { ...snapshot, plan: receipt.plan, analysis: receipt.analysis }
      else if (snapshot.analysis?.run_id !== w.runId && w.kind !== 'studio-export') return
    }
    const context = this.context(w.projectId || w.id)
    if (original.material_origin) this.rememberProject(w.projectId || w.id, { ...context, material_origin: original.material_origin, example_version: original.example_version })
    let event: string | undefined
    let outcome: string | undefined
    let details: Record<string, unknown> = {}
    if (w.kind === 'studio-cover') {
      const job = snapshot.output_variants?.find(v => v.cover_job?.job_id === w.id)?.cover_job
      this.observeCoverJob(w, job)
      return
    } else if (w.kind === 'studio-variant') {
      const variant = snapshot.output_variants?.find(v => v.id === w.id && (!w.runId || v.render_job_id === w.runId))
      const job = snapshot.jobs?.find(j => j.job_id === variant?.render_job_id)
      if (variant && ['completed', 'failed'].includes(variant.status)) {
        event = 'studio_variant_finished'; outcome = variant.status
        details = { strategy_id: variant.strategy_id, framing: variant.framing, error_code: job?.error_code, outro_applied: job?.result?.outro_applied, warning_count: job?.result?.warnings?.length }
      }
    } else if (w.kind === 'studio-export') {
      const job = snapshot.jobs?.find(j => j.job_id === w.id)
      if (job && ['completed', 'failed'].includes(job.status)) {
        event = 'studio_export_finished'; outcome = job.status; details = { duration_ms: job.duration_ms, error_code: job.error_code, outro_applied: job.result?.outro_applied, warning_count: job.result?.warnings?.length }
      }
    } else if (w.kind === 'studio-screen') {
      details = { duration_ms: snapshot.analysis?.duration_ms, error_code: snapshot.analysis?.error_code }
      const automatic = !!snapshot.generation?.auto_start && ['production', 'rendering'].includes(snapshot.analysis?.phase || '')
      if (automatic) {
        // Automatic output skips confirmation: screening ended once production started, whatever came after.
        event = 'studio_screen_finished'; outcome = 'auto_started'
        details = { ...details, duration_ms: undefined, error_code: undefined, recommendation_mode: snapshot.plan?.mode, analysis_mode: snapshot.plan?.recommended_analysis, subtitle_status: snapshot.plan?.local_evidence?.subtitle_status }
      } else if (snapshot.analysis?.status === 'failed' && snapshot.analysis?.phase !== 'production') { event = 'studio_screen_finished'; outcome = 'failed' }
      else if (snapshot.analysis?.status === 'awaiting_confirmation' && snapshot.plan?.id) {
        event = 'studio_screen_finished'
        outcome = ['ai', 'local'].includes(snapshot.plan.mode || '') ? 'recommended' : snapshot.plan.mode
        details = { ...details, recommendation_mode: snapshot.plan.mode, analysis_mode: snapshot.plan.recommended_analysis, subtitle_status: snapshot.plan.local_evidence?.subtitle_status }
      }
    } else if (w.kind === 'studio-generation' && ['completed', 'partial', 'failed'].includes(snapshot.generation?.status || '')) {
      event = 'studio_generation_finished'; outcome = snapshot.generation!.status
      details = { ...generationSummary(snapshot), error_code: ['failed', 'partial'].includes(outcome || '') ? snapshot.generation?.error_code || snapshot.analysis?.error_code : undefined }
    } else if (w.kind === 'studio-production' && snapshot.plan?.id === w.id &&
               ['completed', 'failed'].includes(snapshot.analysis?.status || '')) {
      event = 'studio_production_finished'; outcome = snapshot.analysis!.outcome || snapshot.analysis!.status
      details = { ...snapshot.analysis, analysis_mode: snapshot.plan.confirmed_analysis }
    }
    if (event) {
      this.emitOnce(w, 'finished', event, safeStudioProperties({ ...this.context(w.projectId || w.id), ...details, outcome }))
      if (w.seen.includes('finished')) { w.settled = true; this.persist() }
    }
  }
  observeTasks(w: Watch, tasks: TaskSnapshot[]): void {
    const eligible = tasks.filter(t => t.task_type === 'video_processing' && (utcMillis(t.created_at) ?? -1) >= w.since)
    for (const t of eligible) {
      const created = utcMillis(t.created_at)
      if (t.task_type !== 'video_processing' || created === undefined || created < w.since) continue
      const props = { project_id: w.id, task_id: t.id, telemetry_source: 'backend_task_observed' }
      this.emitOnce(w, `${t.id}:observed`, 'processing_task_observed', props)
      // Some workers omit timestamps. Never invent a start or duration for a missed transition.
      const start = utcMillis(t.started_at)
      const end = utcMillis(t.completed_at)
      if (t.status === 'running' || start !== undefined) this.emitOnce(w, `${t.id}:started`, 'processing_started', {
        ...props, occurred_at: new Date(start ?? created).toISOString(),
        time_basis: start === undefined ? 'task_created_at' : 'task_started_at',
      })
      if (['completed', 'failed', 'cancelled'].includes(t.status)) this.emitOnce(w, `${t.id}:finished`, 'processing_finished', {
        ...props, outcome: t.status, occurred_at: end === undefined ? undefined : new Date(end).toISOString(),
        duration_ms: start !== undefined && end !== undefined && end >= start ? end - start : undefined,
      })
    }
    if (eligible.length > 0 && eligible.every(t => w.seen.includes(`${t.id}:finished`))) {
      w.settled = true
      this.persist()
    }
  }
}
