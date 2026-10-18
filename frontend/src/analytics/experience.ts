/** Decision-oriented onboarding/settings events. Never accept raw configuration objects. */
import { captureBusinessEvent } from './posthog'
import { isConnectionTestErrorCode, safeHttpStatus } from './connectionTestCode'
import { workflow } from './observer'
import { sanitizeProviderValidationProperties, SuccessRateEvent, TELEMETRY_PROVIDERS } from './successRateContract'
import { canonOutcome, errorCode, telemetryId, type Properties } from './workflow'

export type Placement = 'home_setup' | 'settings_model'
export type ExperienceEvent = 'setup_presented' | 'setup_action' | 'import_blocked' | 'settings_section_viewed' | 'example_project_viewed'
const enums: Record<string, readonly string[]> = {
  entry_source: ['home_setup', 'direct'],
  placement: ['home_setup', 'settings_model'], action: ['later', 'open_settings', 'one_click'],
  trigger: ['initial', 'import_blocked', 'auto', 'manual', 'provider_change', 'load', 'edit', 'portrait_preset'],
  section: ['ai', 'publish', 'app', 'feedback'], role: ['analysis', 'vision', 'cover', 'transcription'],
  reason: ['setup_required', 'provider', 'model', 'key'], config_source: ['preset', 'customized'], mode: ['initial', 'update'],
  provider: TELEMETRY_PROVIDERS, // same generated enum as success-rate events (every preset)
  source: ['live', 'cache', 'catalog'], outcome: ['success', 'error', 'blocked', 'unknown'],
  resolution: ['created', 'reused'], material_origin: ['sample', 'user', 'unknown'],
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
/** Settings access check. Never include keys or a full URL. */
export function trackProviderValidation(properties: Record<string, unknown>) {
  captureBusinessEvent(SuccessRateEvent.ProviderValidationFinished, sanitizeProviderValidationProperties(properties))
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
