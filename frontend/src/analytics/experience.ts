/** Decision-oriented onboarding/settings events. Never accept raw configuration objects. */
import { captureBusinessEvent } from './posthog'
import { isConnectionTestErrorCode, safeHttpStatus } from './connectionTestCode'
import { workflow } from './observer'
import { sanitizeProviderValidationProperties, SuccessRateEvent, TELEMETRY_PROVIDERS } from './successRateContract'
import { canonOutcome, errorCode, telemetryId, type Properties } from './workflow'

export type Placement = 'home_setup' | 'settings_model' | 'import_card'
export type SetupStep = 'provider' | 'key' | 'connect'
export type ExperienceEvent = 'setup_presented' | 'setup_action' | 'setup_step_done' | 'import_blocked' | 'settings_section_viewed' | 'example_project_viewed'
const enums: Record<string, readonly string[]> = {
  entry_source: ['home_setup', 'direct'],
  placement: ['home_setup', 'settings_model', 'import_card'], action: ['later', 'open_settings', 'one_click', 'connect_recommended'],
  step: ['provider', 'key', 'connect'],
  trigger: ['initial', 'import_blocked', 'auto', 'manual', 'provider_change', 'load', 'edit', 'portrait_preset'],
  section: ['ai', 'publish', 'app', 'feedback'], role: ['analysis', 'vision', 'cover', 'transcription'],
  reason: ['setup_required', 'provider', 'model', 'key'], config_source: ['preset', 'customized'], mode: ['initial', 'update'],
  provider: TELEMETRY_PROVIDERS, // same generated enum as success-rate events (every preset)
  source: ['live', 'cache', 'catalog'], outcome: ['success', 'error', 'blocked', 'unknown'],
  resolution: ['created', 'reused'], material_origin: ['sample', 'user', 'obs', 'unknown'],
  analysis_mode: ['auto', 'subtitle', 'visual'], transcription_mode: ['whisper_local', 'sensevoice_local', 'cloud', 'unknown'],
  cover_mode: ['ai', 'frame'], capability: ['text', 'multimodal', 'auto'],
  analysis_source: ['preset', 'user', 'none'],
  vision_source: ['preset', 'user', 'follow'],
  cover_source: ['preset', 'user', 'frame', 'none'],
  transcription_source: ['preset', 'user', 'whisper_local', 'sensevoice_local', 'none'],
}
export function safeExperience(value: Record<string, unknown>): Properties {
  const out: Properties = { experience_schema_version: 1 }
  for (const [key, choices] of Object.entries(enums)) {
    let raw: unknown = value[key]
    if (key === 'outcome') raw = canonOutcome(raw)
    if (typeof raw === 'string' && choices.includes(raw)) out[key] = raw
  }
  for (const key of ['brand_outro_enabled', 'changed_connections', 'changed_analysis', 'changed_vision', 'changed_cover', 'changed_transcription', 'preview', 'has_warning', 'defaults_applied', 'analysis_configured', 'vision_configured', 'cover_configured', 'transcription_configured', 'cover_separate', 'vision_follow_lacks_vision']) {
    if (typeof value[key] === 'boolean') out[key] = value[key] as boolean
  }
  for (const key of ['result_count', 'duration_ms', 'example_version']) {
    if (typeof value[key] === 'number' && Number.isFinite(value[key]) && (value[key] as number) >= 0) out[key] = value[key] as number
  }
  for (const key of ['operation_id', 'presentation_id', 'flow_id']) {
    if (typeof value[key] === 'string' && /^t-[a-z0-9-]{10,100}$/.test(value[key] as string)) out[key] = value[key] as string
  }
  if (typeof value.error_code === 'string' && (/^(http_[45][0-9]{2}|network|timeout|unknown|validation)$/.test(value.error_code) || isConnectionTestErrorCode(value.error_code))) out.error_code = value.error_code
  const status = safeHttpStatus(value.http_status)
  if (status) out.http_status = status
  return out
}
export function trackExperience(event: ExperienceEvent, properties: Record<string, unknown>) {
  captureBusinessEvent(event, safeExperience(properties))
}
/** Quiet window for one edit-discovery pair, and for an identical validation repeat. */
export const CAPTURE_QUIET_MS = 1500

/** Connection fields that should rediscover models. Not a telemetry payload. */
export function connectionSignature(value: { connections?: Array<{ id?: string; provider?: string; base_url?: string; api_key?: string | null; image_base_url?: string }> } | null | undefined) {
  return JSON.stringify((value?.connections || []).map(c => [c.id, c.provider, c.base_url, c.api_key ?? '', c.image_base_url]))
}

/** trigger=load, manual, and provider_change always report. trigger=edit reports only after the loaded document changes. */
export function shouldReportModelDiscovery(trigger: string, currentSignature: string, loadedSignature: string | null) {
  return trigger !== 'edit' || currentSignature !== loadedSignature
}

type ExperienceFinish = (outcome: 'completed' | 'failed' | 'blocked', extra?: Record<string, unknown>, error?: unknown) => void
type EditSlot = {
  id: number
  timer: ReturnType<typeof setTimeout> | null
  properties: Record<string, unknown>
  settled: { outcome: 'completed' | 'failed' | 'blocked'; extra: Record<string, unknown>; error?: unknown } | null
  quiet: boolean
  sent: boolean
}
let editSerial = 0
const editSlots = new Map<string, EditSlot>()
const loadedSettings = new Map<string, string>()
let lastValidation = { key: '', at: 0 }

function rememberEdit(slot: EditSlot, outcome: 'completed' | 'failed' | 'blocked', extra: Record<string, unknown>, error?: unknown) {
  // A failure inside the burst is the outcome we keep. A later success must not hide it.
  if (slot.settled?.outcome === 'failed' && outcome !== 'failed') return
  slot.settled = { outcome, extra, error }
}

function emitEdit(slot: EditSlot) {
  if (slot.sent || !slot.settled) return
  slot.sent = true
  if (slot.timer) clearTimeout(slot.timer)
  slot.timer = null
  beginExperience('model_discovery', slot.properties)(slot.settled.outcome, slot.settled.extra, slot.settled.error)
}

/**
 * trigger=edit only. Keystrokes and incremental setting changes in one placement
 * become one requested/finished pair, CAPTURE_QUIET_MS after the last call.
 * The discovery request itself is not delayed here.
 */
export function beginDebouncedEditDiscovery(properties: Record<string, unknown>, quietMs = CAPTURE_QUIET_MS): ExperienceFinish {
  const key = typeof properties.placement === 'string' ? properties.placement : 'default'
  let slot = editSlots.get(key)
  if (!slot || slot.sent) {
    slot = { id: ++editSerial, timer: null, properties, settled: null, quiet: false, sent: false }
    editSlots.set(key, slot)
  }
  const generation = slot.id
  slot.properties = properties
  slot.quiet = false
  if (slot.timer) clearTimeout(slot.timer)
  slot.timer = setTimeout(() => {
    const current = editSlots.get(key)
    if (!current || current.id !== generation || current.sent) return
    current.quiet = true
    current.timer = null
    emitEdit(current)
  }, quietMs)
  let used = false
  return (outcome, extra = {}, error) => {
    if (used) return
    used = true
    const current = editSlots.get(key)
    if (!current || current.id !== generation || current.sent) return
    rememberEdit(current, outcome, extra, error)
    if (current.quiet) emitEdit(current)
  }
}

/** True the first time this placement loads this document, and again when it changes. Failures do not call this. */
export function claimModelSettingsLoad(placement: string, snapshot: unknown): boolean {
  const key = placement || 'default'
  let signature = ''
  try { signature = JSON.stringify(snapshot) } catch { return true }
  if (loadedSettings.get(key) === signature) return false
  loadedSettings.set(key, signature)
  return true
}

/** Settings access check. Never include keys or a full URL.
 * Identical results inside CAPTURE_QUIET_MS collapse; a new result or probe still emits. */
export function trackProviderValidation(properties: Record<string, unknown>) {
  const safe = sanitizeProviderValidationProperties(properties)
  const key = JSON.stringify([safe.provider, safe.base_url_host, safe.result, safe.upstream_error_type, safe.probe_kind, safe.trial_context_ok, safe.trial_rate_limited, safe.trial_json_ok])
  const now = Date.now()
  if (key === lastValidation.key && now - lastValidation.at < CAPTURE_QUIET_MS) return
  lastValidation = { key, at: now }
  captureBusinessEvent(SuccessRateEvent.ProviderValidationFinished, safe)
}
/** The same token gates request + result, including consent changes while awaiting an API. */
export function beginExperience(name: 'model_settings_load' | 'model_discovery' | 'provider_configuration_save' | 'provider_connection_test' | 'example_project_open' | 'output_branding_save', properties: Record<string, unknown>) {
  const generation = workflow.generation(), enabled = workflow.active(generation), started = Date.now()
  const props = safeExperience({ ...properties, operation_id: telemetryId() })
  if (enabled) captureBusinessEvent(`${name}_requested`, props)
  let finished = false
  return (outcome: 'completed' | 'failed' | 'blocked', extra: Record<string, unknown> = {}, error?: unknown) => {
    if (finished) return
    finished = true
    if (enabled && workflow.active(generation)) captureBusinessEvent(`${name}_finished`, safeExperience({
      ...props, ...extra, operation_id: props.operation_id, outcome, duration_ms: Date.now() - started,
      ...(error !== undefined ? { error_code: errorCode(error) } : {}),
    }))
  }
}
