/** Versioned business telemetry. Only explicit UI operations enroll projects. */
export type Properties = Record<string, string | number | boolean | null | undefined>
export type Watch = { kind: 'project' | 'export' | 'bilibili' | 'youtube' | 'studio-screen' | 'studio-production' | 'studio-export'; id: string; projectId?: string; since: number; seen: string[]; settled?: boolean; properties?: Properties; token?: string }
export const WORKFLOW_KEY = 'autoclip.analytics.workflow.v2'
const TTL = 7 * 86400000
const LIMIT = 50

/** Explicit property contract: never spread user/model data into a payload. */
export function safeStudioProperties(value: Record<string, unknown> | null = {}): Properties {
  const input = value && typeof value === 'object' ? value : {}
  const out: Properties = { studio_schema_version: 1 }
  const enums: Record<string, string[]> = {
    source_type: ['file', 'youtube', 'bilibili', 'other_url', 'visual_event', 'content_clip', 'studio', 'legacy'],
    analysis_mode: ['subtitle', 'visual', 'auto'], goal: ['content', 'highlight', 'promo', 'auto'],
    aspect: ['original', 'portrait', 'landscape', 'auto'],
    recommendation_mode: ['ai', 'local', 'manual', 'fallback'],
    subtitle_status: ['available', 'missing', 'invalid', 'unreadable', 'too_large'],
    outcome: ['completed', 'failed', 'partial', 'recommended', 'manual', 'fallback', 'scheduled', 'inbox', 'unknown'],
    download_mode: ['native', 'browser'], gateway: ['bilibili', 'upload-post'],
    title_style: ['plain', 'impact', 'card', 'comic', 'neon', 'arena', 'editorial', 'pixel', 'frosted'],
  }
  for (const [key, allowed] of Object.entries(enums)) {
    if (typeof input[key] === 'string' && allowed.includes(input[key] as string)) out[key] = input[key] as string
  }
  for (const key of ['subtitle_enabled', 'has_subtitle', 'goal_content', 'goal_highlight', 'goal_promo', 'allow_visual_screening', 'scheduled', ...['requested', 'succeeded', 'failed'].flatMap(p => ['content', 'highlight', 'promo'].map(g => `${p}_${g}`))]) {
    if (typeof input[key] === 'boolean') out[key] = input[key] as boolean
  }
  for (const key of ['duration_ms', 'request_duration_ms', 'result_count', 'requested_count', 'succeeded_count', 'failed_count']) {
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
  plan?: { id: string; mode?: string; confirmed_analysis?: string; recommended_analysis?: string; local_evidence?: { subtitle_status?: string } }
  analysis?: { status: string; outcome?: string; duration_ms?: number; error_code?: string; requested_goals?: string[]; succeeded_goals?: string[]; failed_goals?: string[]; result_count?: number } | null
  jobs?: { job_id: string; status: string; duration_ms?: number; error_code?: string }[]
}

/** Storage and capture are injected so offline/privacy/replay behavior is testable. */
export class WorkflowTracker {
  private watches: Watch[] = []
  private epoch = 0
  constructor(
    private storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>,
    private enabled: () => boolean,
    private capture: (event: string, properties: Properties) => boolean,
    private now: () => number = Date.now,
  ) {
    try {
      const raw: unknown = JSON.parse(storage.getItem(WORKFLOW_KEY) || '[]')
      if (Array.isArray(raw)) this.watches = raw.filter((w): w is Watch =>
        w && ['project', 'export', 'bilibili', 'youtube', 'studio-screen', 'studio-production', 'studio-export'].includes(w.kind) &&
        typeof w.id === 'string' && Number.isFinite(w.since) && Array.isArray(w.seen) &&
        w.seen.every((v: unknown) => typeof v === 'string') && w.seen.length <= 2000 &&
        (w.projectId === undefined || typeof w.projectId === 'string'))
    } catch { /* corrupted/unavailable storage cannot block the application */ }
    this.prune()
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
    try { this.storage.removeItem(WORKFLOW_KEY) } catch { /* best effort */ }
  }
  generation(): number { return this.epoch }
  active(generation: number): boolean { return generation === this.epoch && this.enabled() }
  list(): Watch[] {
    if (!this.enabled()) { this.clear(); return [] }
    this.prune()
    return [...this.watches]
  }
  watch(kind: Watch['kind'], id: string, projectId?: string, since = this.now(), properties: Properties = {}, restart = false): void {
    if (!this.enabled() || !id) return
    this.prune()
    const existing = this.watches.find(w => w.kind === kind && w.id === id)
    if (existing && (!existing.settled || kind === 'studio-export') && !restart) return
    if (existing) this.watches = this.watches.filter(w => w !== existing)
    this.watches.push({ kind, id, projectId, since, seen: [], properties: safeStudioProperties(properties), token: `${this.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}` })
    this.prune()
    this.persist()
  }
  emitOnce(w: Watch, key: string, event: string, properties: Properties): void {
    if (!this.enabled() || !this.watches.includes(w) || w.seen.includes(key) || w.seen.length >= 2000) return
    if (this.capture(event, w.kind.startsWith('studio-') ? { ...safeStudioProperties(w.properties), ...safeStudioProperties(properties), ...(w.token && /^[a-z0-9-]{10,100}$/.test(w.token) ? { $insert_id: `studio-v1:${w.token}:${key}` } : {}) } : { ...properties, $insert_id: `autoclip-v2:${w.kind}:${w.id}:${key}` })) {
      w.seen.push(key)
      this.persist()
    }
  }
  /** IDs remain in local watches only; external payload follows the versioned aggregate contract. */
  observeStudio(w: Watch, snapshot: StudioSnapshot): void {
    if (w.settled) return
    let event: string | undefined
    let outcome: string | undefined
    let details: Record<string, unknown> = {}
    if (w.kind === 'studio-export') {
      const job = snapshot.jobs?.find(j => j.job_id === w.id)
      if (job && ['completed', 'failed'].includes(job.status)) {
        event = 'studio_export_finished'; outcome = job.status; details = { duration_ms: job.duration_ms, error_code: job.error_code }
      }
    } else if (w.kind === 'studio-screen') {
      details = { duration_ms: snapshot.analysis?.duration_ms, error_code: snapshot.analysis?.error_code }
      if (snapshot.analysis?.status === 'failed') { event = 'studio_screen_finished'; outcome = 'failed' }
      else if (snapshot.analysis?.status === 'awaiting_confirmation' && snapshot.plan?.id) {
        event = 'studio_screen_finished'
        outcome = ['ai', 'local'].includes(snapshot.plan.mode || '') ? 'recommended' : snapshot.plan.mode
        details = { ...details, recommendation_mode: snapshot.plan.mode, analysis_mode: snapshot.plan.recommended_analysis, subtitle_status: snapshot.plan.local_evidence?.subtitle_status }
      }
    } else if (w.kind === 'studio-production' && snapshot.plan?.id === w.id &&
               ['completed', 'failed'].includes(snapshot.analysis?.status || '')) {
      event = 'studio_production_finished'; outcome = snapshot.analysis!.outcome || snapshot.analysis!.status
      details = { ...snapshot.analysis, analysis_mode: snapshot.plan.confirmed_analysis }
    }
    if (event) {
      this.emitOnce(w, 'finished', event, safeStudioProperties({ ...details, outcome }))
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
