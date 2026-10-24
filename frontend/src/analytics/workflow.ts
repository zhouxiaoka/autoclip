import { ERROR_CODE } from './failureCodes'
/** Versioned business telemetry. Only explicit UI operations enroll projects. */
export type Properties = Record<string, string | number | boolean | null | undefined>
export type Watch = { kind: 'project' | 'export' | 'bilibili' | 'youtube' | 'studio-screen' | 'studio-production' | 'studio-export' | 'studio-generation' | 'studio-cover' | 'studio-variant' | 'framing-runtime'; id: string; projectId?: string; since: number; seen: string[]; settled?: boolean; properties?: Properties; token?: string; runId?: string; attemptId?: string }
export const WORKFLOW_KEY = 'autoclip.analytics.workflow.v2'
const TTL = 7 * 86400000
const LIMIT = 50
const CONTEXT_KEY = "autoclip.analytics.context.v1"
// Random base36 segments joined by '-' can spell a secret marker (e.g. a segment ending in "sk"
// followed by '-' gives "sk-"), which the privacy check rightly flags. Ids must never contain one.
// Keep in sync with event_catalog privacy.forbidden_substrings and backend llm_telemetry markers.
export const ID_FORBIDDEN_MARKERS = ['sk-', 'xai-', 'aiza', 'apikey', 'token']
const hasMarker = (id: string) => ID_FORBIDDEN_MARKERS.some(marker => id.includes(marker))
export function telemetryId(): string {
  const make = () => `t-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`
  let id = make()
  for (let tries = 0; tries < 8 && hasMarker(id); tries++) id = make()
  // Deterministic last resort (e.g. a stuck RNG): break every marker without changing the id shape.
  while (hasMarker(id)) id = id.replace(/sk-/g, 's0-').replace(/xai-/g, 'xa0-').replace(/aiza/g, 'ai0a').replace(/apikey/g, 'api0ey').replace(/token/g, 't0ken')
  return id
}
/** firstClips: generation identities that already reported first clip. */
type Context = { props: Properties; updated: number; artifacts: Record<string, string>; firstClips?: string[] }
/** The backend's attempt receipt (backend/services/studio/attempts.py). The frontend never creates attempts:
 * attempt_id, retry_of and order (sequence) come from here, not from local watches or timestamps. */
export interface AttemptReceipt {
  attempt_id: string; flow_id: string; sequence: number; retry_of?: string | null; kind: 'generation' | 'production'
  trigger?: string; state: 'open' | 'completed' | 'partial' | 'failed' | 'abandoned'; run_id?: string | null
  causes?: { goal?: string | null; stage?: string; code?: string; upstream?: string; identity?: string }[]
  error_code?: string; failure_stage?: string | null; upstream_error_type?: string | null
  secondary_error_codes?: string[]; secondary_upstream_error_types?: string[]; secondary_failure_stages?: string[]
  summary?: Record<string, unknown>
  degrade_reason?: string  // frozen from the attempt's own plan at settle (enum)
}
const TOKEN = /^t-[a-z0-9-]{10,100}$/

const OS_CANON: Record<string, string> = { darwin: 'macos', win32: 'windows' }
const OUTCOME_CANON: Record<string, string> = { completed: 'success', failed: 'error' }

/** 1.5.7 send contract: only macos/windows/linux/unknown. */
export function canonOs(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  return OS_CANON[value] || value
}

/** 1.5.7 send contract: completed→success, failed→error.
 * Legacy `processing_finished` keeps `cancelled` (user abort is not a product error). */
export function canonOutcome(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  return OUTCOME_CANON[value] || value
}

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
    trigger: ['auto', 'manual', 'portrait_preset', 'hover', 'focus', 'keyboard', 'button', 'select', 'paste', 'drop', 'radar', 'watch', 'initial', 'retry', 'variant_retry', 'append_platform'], framing_outcome: ['framed', 'no_detection'],
    framing_status: ['installed', 'installing', 'failed', 'missing', 'not_installed', 'error'],
    source_type: ['file', 'youtube', 'bilibili', 'other_url', 'visual_event', 'content_clip', 'studio', 'legacy'],
    analysis_mode: ['subtitle', 'visual', 'auto'], goal: ['content', 'highlight', 'promo', 'auto'],
    aspect: ['original', 'portrait', 'landscape', 'auto'],
    portrait_style: ['auto', 'interview', 'podcast'], artifact_type: ['video', 'publish_kit', 'combined', 'cover_3x4'],
    recommendation_mode: ['ai', 'local', 'manual', 'fallback'],
    degrade_reason: ['vision_unavailable_subtitle_fallback', 'vision_invalid_subtitle_fallback', 'frame_extract_subtitle_fallback', 'source_too_long_subtitle_route'],
    subtitle_status: ['available', 'missing', 'invalid', 'unreadable', 'too_large'],
    outcome: ['success', 'error', 'partial', 'downgraded', 'skipped', 'recommended', 'manual', 'fallback', 'scheduled', 'inbox', 'unknown', 'auto_started'],
    download_mode: ['native', 'browser'], gateway: ['bilibili', 'upload-post'],
    title_style: ['plain', 'impact', 'card', 'comic', 'neon', 'arena', 'editorial', 'pixel', 'frosted'],
    share_target: ['copy_caption', 'use_case_discussion', 'copy_and_save'],
    output_rating: ['ready', 'needs_edit', 'unusable'],
    template: ['interview_zh', 'podcast_en', 'landscape', 'none', 'editorial', 'street', 'news', 'cinema', 'classic'],
    requested_template: ['interview_zh', 'podcast_en', 'landscape', 'none', 'editorial', 'street', 'news', 'cinema', 'classic'],
    from_template: ['interview_zh', 'podcast_en', 'landscape', 'none', 'editorial', 'street', 'news', 'cinema', 'classic'],
    to_template: ['interview_zh', 'podcast_en', 'landscape', 'none', 'editorial', 'street', 'news', 'cinema', 'classic'],
    recommended: ['interview_zh', 'podcast_en', 'landscape', 'none', 'editorial', 'street', 'news', 'cinema', 'classic'],
    recommended_template: ['interview_zh', 'podcast_en', 'landscape', 'none', 'editorial', 'street', 'news', 'cinema', 'classic'],
    reason_code: ['seated_interview', 'street_quick', 'speech', 'default', 'timeout'],
    flag_variant: ['visual', 'text'],
    source_kind: ['link', 'file', 'none'],
    input: ['mouse', 'keyboard'],
    error_kind: ['decode', 'stalled', 'unsupported', 'unknown'],
    encoder: ['libx264', 'h264_nvenc', 'h264_qsv', 'h264_amf', 'h264_videotoolbox'],
    downgrade_reason: ['none', 'over_budget', 'missing_runtime', 'intel_mac_unverified', 'rank', 'flag_off', 'capture', 'encode'],
    failure_reason: ['none', 'capture', 'encode', 'runtime', 'timeout', 'unknown'],
    os: ['macos', 'windows', 'linux', 'unknown'],
    stage: ['pre_import', 'results_chip', 'editor'],
    packaging_style: ['classic', 'boxed', 'spotlight', 'pop', 'cinematic'],
    framing: ['speaker', 'full_frame', 'full_frame_pending', 'full_frame_captions'],
    qa_checker: ['avsync', 'face', 'loudness', 'jitter', 'ending'],
    qa_outcome: ['pass', 'fail', 'skip'],
    qa_bucket: ['lt40', '40_80', '80_200', 'gt200', 'start_only', 'none', 'lt10', '10_40', 'gt40', 'in_target', 'quiet_1_3', 'quiet_gt3', 'loud_1_3', 'loud_gt3', 'peak', 'peak_and_level', 'calm', 'flash', 'rms', 'flash_and_rms', 'complete', 'mid_word', 'mid_sentence', 'timeout', 'budget', 'no_audio', 'no_detector', 'no_words', 'unreadable', 'error'],
    qa_avsync: ['pass', 'fail', 'skip'], qa_face: ['pass', 'fail', 'skip'], qa_loudness: ['pass', 'fail', 'skip'], qa_jitter: ['pass', 'fail', 'skip'], qa_ending: ['pass', 'fail', 'skip'],
    qa_mode: ['shadow'],
    failure_stage: ['screening', 'dispatch', 'production', 'ingest', 'subtitle', 'analyze', 'vision', 'render', 'outline', 'timeline', 'scoring', 'title', 'clustering', 'other'],
    route: ['subtitle', 'visual'],
    provider: ['apimart', 'api88', 'infistar', 'deepseek', 'dashscope', 'siliconflow', 'seed', 'glm', 'kimi', 'minimax-cn', 'xiaomi', 'openai', 'gemini', 'whisper', 'sensevoice', 'ollama', 'lmstudio', 'openrouter', 'anthropic', 'grok', 'groq', 'mistral', 'together', 'fireworks', 'huggingface', 'nvidia', 'cerebras', 'baseten', 'azure-openai', 'amazon-bedrock', 'google-vertex', 'cloudflare-workers-ai', 'cloudflare-ai-gateway', 'vercel-ai-gateway', 'moonshotai', 'minimax', 'ant-ling', 'qianfan', 'hunyuan', 'byteplus-modelark', 'compatible', 'other', 'whisper_local', 'sensevoice_local', 'cloud'],
    config_source: ['preset', 'customized'],
    attribution_source: ['request', 'phase', 'local'],
    shutdown_kind: ['clean', 'parent_lost', 'crash', 'unknown'],
    upstream_error_type: ['invalid_key', 'insufficient_quota', 'permission_denied', 'model_not_found', 'bad_endpoint', 'rate_limited', 'upstream_unavailable', 'timeout', 'connection', 'output_truncated', 'unknown'],
    code: ['whisper_installed', 'whisper_installing', 'whisper_install_failed', 'whisper_not_installed', 'whisper_model_downloading', 'whisper_model_failed', 'whisper_model_missing', 'sensevoice_ready', 'sensevoice_not_ready', 'cloud_configured', 'cloud_not_configured'],
    platform_source: ['remembered', 'accounts', 'locale', 'user'],
    transcription_route: ['platform_subs', 'whisper', 'cloud', 'srt'],
    field: ['platform', 'clip_count', 'duration', 'clip_swap', 'clip_delete', 'title', 'layout', 'not_exported'],
    kind: ['first_clip', 'all_done', 'failed'],
    permission: ['granted', 'denied', 'default'],
    legacy_action: ['start_processing', 'collection', 'export_confirm', 'plan_adjust', 'preferences'],
  }
  for (const [key, allowed] of Object.entries(enums)) {
    let raw: unknown = input[key]
    if (key === 'os') raw = canonOs(raw)
    if (key === 'outcome') raw = canonOutcome(raw)
    if (typeof raw === 'string' && allowed.includes(raw)) out[key] = raw
  }
  for (const key of ['outro_applied', 'brand_outro_enabled', 'reused_content_profile', 'has_crop_track', 'has_manual_adjustment', 'auto_frame_retained', 'tags_enabled', 'packaging_fallback', 'burned_captions', 'subtitle_enabled', 'has_subtitle', 'blocked', 'goal_content', 'goal_highlight', 'goal_promo', 'allow_visual_screening', 'scheduled', 'is_recommended', 'accepted_recommendation', ...['requested', 'succeeded', 'failed'].flatMap(p => ['content', 'highlight', 'promo'].map(g => `${p}_${g}`))]) {
    if (typeof input[key] === 'boolean') out[key] = input[key] as boolean
  }
  if (typeof input.downgraded === 'boolean') out.downgraded = input.downgraded
  for (const key of ['warning_count', 'outro_applied_count', 'outro_fallback_count', 'outro_unknown_count', 'full_frame_count', 'framing_pending_count', 'framing_captions_count', 'example_version', 'framed_count', 'scene_count', 'fit_count', 'duration_ms', 'request_duration_ms', 'ttfc_ms', 'stage_ms_download', 'stage_ms_transcribe', 'stage_ms_analyze', 'stage_ms_render', 'latency_ms', 'first_frame_ms', 'variant_count', 'completed_variant_count', 'failed_variant_count', 'skipped_variant_count', 'on_demand_variant_count', 'interview_count', 'podcast_count', 'landscape_count', 'editorial_count', 'street_count', 'news_count', 'cinema_count', 'classic_count', 'html_downgrade_count', 'speaker_framed_count', 'packaging_fallback_count', 'trimmed_count', 'platform_count', 'result_count', 'requested_count', 'succeeded_count', 'failed_count', 'cpu_count', 'retry_count', 'degrade_count', 'billable_calls_before_failure', 'prompt_tokens', 'completion_tokens', 'reasoning_tokens', 'llm_calls']) {
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
  // the backend receipt's per-project sequence; success_rate.sql orders a flow's attempts by it.
  if (typeof input.attempt_sequence === 'number' && Number.isInteger(input.attempt_sequence) && input.attempt_sequence >= 1) out.attempt_sequence = input.attempt_sequence
  if (typeof input.http_status === 'number' && Number.isInteger(input.http_status) && input.http_status >= 400 && input.http_status <= 599) out.http_status = input.http_status
  if (typeof input.error_code === 'string' && ERROR_CODE.test(input.error_code)) out.error_code = input.error_code
  // the other causes of a multi-goal failure, positional, comma-joined (primary is error_code / upstream_error_type).
  // Arrays from the backend, or the joined string when an already-safe payload is sanitized again.
  const causes = (v: unknown): unknown[] | undefined => Array.isArray(v) ? v : typeof v === 'string' ? v.split(',') : undefined
  const codes = causes(input.secondary_error_codes), upstreams = causes(input.secondary_upstream_error_types)
  if (codes) out.secondary_error_codes = codes.slice(0, 3).map(c => typeof c === 'string' && ERROR_CODE.test(c) ? c : 'unknown').join(',')
  if (upstreams) out.secondary_upstream_error_types = upstreams.slice(0, 3).map(c => typeof c === 'string' && enums.upstream_error_type.includes(c) ? c : '').join(',')
  if (typeof input.model === 'string' && /^[\w.\-:/]{1,64}$/.test(input.model) && !input.model.toLowerCase().includes('sk-') && !input.model.includes('://')) out.model = input.model
  if (typeof input.base_url_host === 'string' && (input.base_url_host === 'local' || /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*)$/.test(input.base_url_host))) out.base_url_host = input.base_url_host
  for (const key of ['flow_id', 'operation_id', 'artifact_id', 'attempt_id', 'retry_of']) {
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

export interface StudioQaCheck { checker?: string; outcome?: string; bucket?: string; duration_ms?: number }
export interface StudioQa { mode?: string; checks?: StudioQaCheck[] }

export interface TaskSnapshot {
  id: string; task_type: string; status: string; created_at: string
  started_at?: string | null; completed_at?: string | null
}

export interface StudioSnapshot {
  material_origin?: 'sample' | 'user' | 'unknown'
  example_version?: number
  attempts?: AttemptReceipt[]
  analysis_history?: { run_id: string; plan?: StudioSnapshot['plan']; analysis: StudioSnapshot['analysis'] }[]
  plan?: { id: string; mode?: string; confirmed_analysis?: string; recommended_analysis?: string; degrade_reason?: 'vision_unavailable_subtitle_fallback' | 'vision_invalid_subtitle_fallback' | 'frame_extract_subtitle_fallback' | 'source_too_long_subtitle_route'; local_evidence?: { subtitle_status?: string } }
  analysis?: { run_id?: string; phase?: string; status: string; outcome?: string; duration_ms?: number; error_code?: string; failure_stage?: string; http_status?: number; provider?: string; config_source?: string; screening_identity?: { provider?: string; config_source?: string }; shutdown_kind?: string; model?: string; base_url_host?: string; upstream_error_type?: string; attribution_source?: string; billable_calls_before_failure?: number; retry_count?: number; degrade_count?: number; llm_calls?: number; prompt_tokens?: number; completion_tokens?: number; requested_goals?: string[]; succeeded_goals?: string[]; failed_goals?: string[]; result_count?: number } | null
  jobs?: { job_id: string; status: string; duration_ms?: number; finished_at?: string; error_code?: string; brand_outro?: boolean; result?: { outro_applied?: boolean; warnings?: string[]; template_render?: { template?: string; requested_template?: string; downgraded?: boolean; downgrade_reason?: string; encoder?: string; duration_ms?: number; failure_reason?: string; outcome?: string; os?: string; cpu_count?: number } }; qa?: StudioQa | null }[]
  generation?: { auto_start?: boolean; attempt_id?: string; status?: string; screening_identity?: { provider?: string; config_source?: string }; error_code?: string; failure_stage?: string; http_status?: number; provider?: string; config_source?: string; shutdown_kind?: string; model?: string; base_url_host?: string; upstream_error_type?: string; attribution_source?: string; billable_calls_before_failure?: number; retry_count?: number; degrade_count?: number; llm_calls?: number; prompt_tokens?: number; completion_tokens?: number; route?: string; portrait_style?: string; branding?: { outro_enabled?: boolean }; requested_platforms?: string[]; completed_variant_count?: number; skipped?: unknown[]; source_has_burned_subtitles?: boolean; created_at?: string; finished_at?: string; recommended_template?: string; accepted_recommendation?: boolean } | null
  output_variants?: { id?: string; draft_id: string; render_job_id?: string; render_attempt_id?: string; preparation_run_id?: string; strategy_id: string; status: string; framing?: string; branding?: { outro_enabled?: boolean }; trimmed_to_sec?: number; cover_job?: { job_id: string; status: string } | null; qa?: StudioQa | null }[]
  drafts?: { id: string; packaging?: { template?: string; fallback?: boolean } | null }[]
}

/** Aggregate counts for one automatic generation; no titles, captions, names or IDs. */
/** screening's own provider/config_source. Production re-freezes ``analysis.provider`` by its
 * route, so screen_finished reads the identity screening stored apart (older records: the flat fields). */
export function screeningIdentity(snapshot: StudioSnapshot): { provider?: string; config_source?: string } {
  const analysis = snapshot.analysis
  for (const own of [analysis?.screening_identity, snapshot.generation?.auto_start ? snapshot.generation.screening_identity : undefined]) {
    if (own && own.provider && own.config_source) return { provider: own.provider, config_source: own.config_source }
  }
  const own = pickAttribution(analysis)
  return own.provider ? { provider: own.provider as string, config_source: own.config_source as string } : {}
}

type Attributed = { attribution_source?: string; provider?: string; config_source?: string; model?: string; base_url_host?: string; http_status?: number; upstream_error_type?: string; failure_stage?: string; status?: string; outcome?: string } | null | undefined
const ATTRIBUTION_SOURCES = ['request', 'phase', 'local']
const FAILED = ['failed', 'partial']

/** same rule as backend failure_attribution.is_failed_terminal: status OR outcome failed/partial
 * (completed + outcome=partial is a valid partial); no status at all -> undecided (null). */
export function isFailedTerminal(record: Attributed): boolean | null {
  if (!record) return false
  if (FAILED.includes(record.status || '') || FAILED.includes(record.outcome || '')) return true
  return record.status ? false : null
}

/** THE frontend attribution serializer (twin of backend failure_attribution
 * export_attribution). The only keys that can come out, copied one by one and type-checked. */
export const ATTRIBUTION_KEYS = Object.freeze(['provider', 'config_source', 'model', 'base_url_host', 'attribution_source', 'http_status', 'upstream_error_type', 'failure_stage'] as const)
const IDENTITY_KEYS = ['provider', 'config_source', 'model', 'base_url_host'] as const

function validAttributionValue(key: string, value: unknown): boolean {
  if (key === 'http_status') return typeof value === 'number' && Number.isInteger(value) && value >= 400 && value <= 599
  if (key === 'attribution_source') return typeof value === 'string' && ATTRIBUTION_SOURCES.includes(value)
  return typeof value === 'string' && value !== ''
}

/** THE frontend attribution reader, the same rules as backend read_attribution. It reads
 * ONE record's snapshot: the caller picks the record (the event's own terminal), never several.
 * Identity only as a provider/config_source pair; failure fields only on a failed (or undecided) terminal,
 * and never status/upstream on ``local``. an explicit whitelist (ATTRIBUTION_KEYS), every value
 * type-checked, the result frozen; ``omitIdentity`` serves screen events (their identity is screening's own). */
export function pickAttribution(record: Attributed, options: { omitIdentity?: boolean } = {}): Readonly<Record<string, unknown>> {
  if (!record) return Object.freeze({})
  const raw = record as Record<string, unknown>
  const clean: Record<string, unknown> = {}
  for (const key of ATTRIBUTION_KEYS) if (validAttributionValue(key, raw[key])) clean[key] = raw[key]
  const out: Record<string, unknown> = {}
  if (!options.omitIdentity && clean.provider && clean.config_source) for (const key of IDENTITY_KEYS) if (key in clean) out[key] = clean[key]
  const source = clean.attribution_source as string | undefined
  if (source) out.attribution_source = source
  if (isFailedTerminal(record) !== false) {
    if ('failure_stage' in clean) out.failure_stage = clean.failure_stage
    if (source !== 'local') for (const key of ['http_status', 'upstream_error_type'] as const) if (key in clean) out[key] = clean[key]
  }
  return Object.freeze(out)
}

/** Time from generation.created_at to the first completed render. No observer clock, no titles. */
export function firstClipReady(snapshot: StudioSnapshot): Record<string, unknown> | null {
  const created = utcMillis(snapshot.generation?.created_at)
  if (created === undefined) return null
  const jobs = new Map((snapshot.jobs || []).map(job => [job.job_id, job]))
  const drafts = new Map((snapshot.drafts || []).map(draft => [draft.id, draft]))
  const ready = (snapshot.output_variants || []).flatMap(variant => {
    const job = variant.render_job_id ? jobs.get(variant.render_job_id) : undefined
    const finished = utcMillis(job?.finished_at)
    if (variant.status !== 'completed' || finished === undefined) return []
    return [{ variant, job, finished }]
  }).sort((left, right) => left.finished - right.finished)
  const first = ready[0]
  if (!first) return null
  const template = drafts.get(first.variant.draft_id)?.packaging?.template
  const render = first.job?.duration_ms
  return {
    ttfc_ms: Math.max(0, first.finished - created),
    strategy_id: first.variant.strategy_id,
    ...(template ? { template } : {}),
    ...(typeof render === 'number' && Number.isFinite(render) && render >= 0 ? { stage_ms_render: render } : {}),
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
          this.contexts[key] = { props: safeStudioProperties(c.props), updated: c.updated, artifacts: Object.fromEntries(Object.entries(c.artifacts || {}).filter(([,v]) => typeof v === 'string' && TOKEN.test(v)).slice(-100)),
            ...(Array.isArray(c.firstClips) ? { firstClips: c.firstClips.filter((v): v is string => typeof v === 'string' && v.length <= 64).slice(-50) } : {}) }
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
    this.contexts[id] = { ...before, props: { ...before?.props, ...props, flow_id: before?.props.flow_id || props.flow_id || telemetryId() }, updated: this.now(), artifacts: before?.artifacts || {} }
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
  watch(kind: Watch['kind'], id: string, projectId?: string, since = this.now(), properties: Properties = {}, restart = false, runId?: string, attemptId?: string): void {
    if (!this.enabled() || !id) return
    this.prune()
    // restart = a new run of this subject: it supersedes every earlier watch, whatever run it watched.
    const existing = this.watches.find(w => w.kind === kind && w.id === id && (restart || !runId || w.runId === runId))
    if (existing && (!existing.settled || kind === 'studio-export') && !restart) return
    if (existing) this.watches = this.watches.filter(w => w !== existing)
    this.watches.push({ kind, id, runId, attemptId: attemptId && TOKEN.test(attemptId) ? attemptId : undefined, projectId, since, seen: [], properties: safeStudioProperties({ ...this.context(projectId || id), ...properties }), token: telemetryId() })
    this.prune()
    this.persist()
  }
  /** One watch per attempt so a lost import response still follows first-clip and completion notices. */
  watchAttempt(projectId: string, receipt: Pick<AttemptReceipt, 'attempt_id' | 'kind' | 'run_id'> | null | undefined, properties: Properties = {}, planId?: string): void {
    if (!receipt || !TOKEN.test(receipt.attempt_id)) return
    const kind = receipt.kind === 'production' ? 'studio-production' : 'studio-generation'
    if (this.watches.some(w => w.attemptId === receipt.attempt_id)) return
    this.watch(kind, kind === 'studio-production' ? (planId || projectId) : projectId, kind === 'studio-production' ? projectId : undefined, this.now(), properties, false, receipt.run_id || receipt.attempt_id, receipt.attempt_id)
  }
  /** A lost import response still leaves the open attempt on the workspace; adopt that watch. */
  adoptOpenAttempt(projectId: string, snapshot: Pick<StudioSnapshot, 'attempts'> | null | undefined): void {
    for (const receipt of (Array.isArray(snapshot?.attempts) ? snapshot.attempts : []))
      if (receipt.state === 'open' && receipt.kind === 'generation') this.watchAttempt(projectId, receipt)
  }
  emitOnce(w: Watch, key: string, event: string, properties: Properties, attemptId?: string): void {
    if (!this.enabled() || !this.watches.includes(w) || w.seen.includes(key) || w.seen.length >= 2000) return
    const id = attemptId || w.token
    if (this.capture(event, (w.kind.startsWith('studio-') || w.kind === 'framing-runtime') ? { ...safeStudioProperties(w.properties), ...safeStudioProperties(properties), ...safeStudioProperties({ attempt_id: id }), ...(id && /^[a-z0-9-]{10,100}$/.test(id) ? { $insert_id: `studio-v1:${id}:${key}` } : {}) } : { ...this.context(w.projectId || w.id), ...properties, $insert_id: `autoclip-v2:${w.kind}:${w.id}:${key}` })) {
      w.seen.push(key)
      this.persist()
    }
  }
  /** First completed render of a watched generation. Caller decides whether the flag was assigned. */
  noteFirstClip(w: Watch, snapshot: StudioSnapshot, assigned: boolean): void {
    if (!assigned || w.kind !== 'studio-generation') return
    const ready = firstClipReady(snapshot)
    if (!ready) return
    // Dedupe by the real generation (created_at), not by the watch: a retry's new watch must not re-report it.
    const pid = w.projectId || w.id, identity = String(snapshot.generation?.created_at || '').slice(0, 64)
    const c = this.contexts[pid]
    if (!identity || c?.firstClips?.includes(identity)) return
    const before = w.seen.length
    this.emitOnce(w, 'first-clip', 'studio_first_clip_ready', safeStudioProperties({ ...this.context(w.projectId || w.id), ...ready }))
    if (w.seen.length > before && this.contexts[pid]) { this.contexts[pid].firstClips = [...(this.contexts[pid].firstClips || []), identity].slice(-50); this.persistContexts() }
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
    const v4 = w.kind === 'studio-generation' || w.kind === 'studio-production'
    if (w.runId && w.kind !== 'studio-variant' && !v4) {
      const receipt = snapshot.analysis_history?.find(r => r.run_id === w.runId)
      // a replayed run reads its OWN receipt; never borrow the current round's screening identity.
      if (receipt) snapshot = { ...snapshot, plan: receipt.plan, analysis: receipt.analysis, generation: snapshot.generation && { ...snapshot.generation, screening_identity: undefined } }
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
      // runId is the attempt identity the API returned: render job, render attempt, or preparation run.
      const variant = snapshot.output_variants?.find(v => v.id === w.id && (!w.runId || [v.render_job_id, v.render_attempt_id, v.preparation_run_id].includes(w.runId)))
      const job = snapshot.jobs?.find(j => j.job_id === variant?.render_job_id)
      if (variant && ['completed', 'failed'].includes(variant.status)) {
        event = 'studio_variant_finished'; outcome = variant.status
        details = { strategy_id: variant.strategy_id, framing: variant.framing, error_code: job?.error_code, outro_applied: job?.result?.outro_applied, warning_count: job?.result?.warnings?.length }
        const report = job?.result?.template_render
        if (report) this.emitOnce(w, 'template', 'studio_template_render_finished', safeStudioProperties({ ...this.context(w.projectId || w.id), ...report, strategy_id: variant.strategy_id }))
      }
    } else if (w.kind === 'studio-export') {
      const job = snapshot.jobs?.find(j => j.job_id === w.id)
      if (job && ['completed', 'failed'].includes(job.status)) {
        event = 'studio_export_finished'; outcome = job.status; details = { duration_ms: job.duration_ms, error_code: job.error_code, outro_applied: job.result?.outro_applied, warning_count: job.result?.warnings?.length }
      }
    } else if (w.kind === 'studio-screen') {
      // the screen event carries the analysis record's attribution (incl. attribution_source) via
      // pickAttribution; the identity is still screening's own.
      details = { duration_ms: snapshot.analysis?.duration_ms, error_code: snapshot.analysis?.error_code, ...pickAttribution(snapshot.analysis, { omitIdentity: true }), ...screeningIdentity(snapshot), shutdown_kind: snapshot.analysis?.shutdown_kind, degrade_reason: snapshot.plan?.degrade_reason }
      const automatic = !!snapshot.generation?.auto_start && ['production', 'rendering'].includes(snapshot.analysis?.phase || '')
      if (automatic) {
        // Automatic output skips confirmation: screening ended once production started, whatever came after.
        event = 'studio_screen_finished'; outcome = 'auto_started'
        details = { ...details, duration_ms: undefined, error_code: undefined, failure_stage: undefined, upstream_error_type: undefined, http_status: undefined, recommendation_mode: snapshot.plan?.mode, analysis_mode: snapshot.plan?.recommended_analysis, subtitle_status: snapshot.plan?.local_evidence?.subtitle_status }
      } else if (isFailedTerminal(snapshot.analysis) === true && snapshot.analysis?.phase !== 'production') { event = 'studio_screen_finished'; outcome = 'failed' }
      else if (snapshot.analysis?.status === 'awaiting_confirmation' && snapshot.plan?.id) {
        event = 'studio_screen_finished'
        outcome = ['ai', 'local'].includes(snapshot.plan.mode || '') ? 'recommended' : snapshot.plan.mode
        details = { ...details, recommendation_mode: snapshot.plan.mode, analysis_mode: snapshot.plan.recommended_analysis, subtitle_status: snapshot.plan.local_evidence?.subtitle_status }
      }
    } else if (v4) return
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
      this.emitOnce(w, `${t.id}:observed`, 'processing_task_observed', { ...props, legacy: true })
      // Some workers omit timestamps. Never invent a start or duration for a missed transition.
      const start = utcMillis(t.started_at)
      const end = utcMillis(t.completed_at)
      if (t.status === 'running' || start !== undefined) this.emitOnce(w, `${t.id}:started`, 'processing_started', {
        ...props, legacy: true, occurred_at: new Date(start ?? created).toISOString(),
        time_basis: start === undefined ? 'task_created_at' : 'task_started_at',
      })
      if (['completed', 'failed', 'cancelled'].includes(t.status)) this.emitOnce(w, `${t.id}:finished`, 'processing_finished', {
        ...props, outcome: canonOutcome(t.status) || t.status, legacy: true,
        occurred_at: end === undefined ? undefined : new Date(end).toISOString(),
        duration_ms: start !== undefined && end !== undefined && end >= start ? end - start : undefined,
      })
    }
    if (eligible.length > 0 && eligible.every(t => w.seen.includes(`${t.id}:finished`))) {
      w.settled = true
      this.persist()
    }
  }
}
