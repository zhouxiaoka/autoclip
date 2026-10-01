import { captureBusinessEvent } from './posthog'
import { workflow } from './observer'
import { errorCode, safeStudioProperties, telemetryId, type Properties, type StudioSnapshot } from './workflow'

/** Only allowlisted values and randomly generated telemetry correlation tokens leave the app.
 * Internal project/job IDs, URLs, filenames, content and model output stay local. */
export async function observeStudioOperation<T>(
  name: 'studio_import' | 'studio_confirm' | 'studio_export' | 'studio_rescreen' | 'studio_plan_update' | 'studio_draft_create' | 'studio_draft_save' | 'studio_draft_duplicate' | 'studio_rewrite' | 'studio_analysis_preferences' | 'vision_provider_test' | 'vision_provider_save' | 'social_publish' | 'studio_auto_frame' | 'studio_framing_install' | 'studio_platform_append' | 'studio_variant_retry' | 'studio_variant_produce' | 'studio_post_save' | 'studio_cover_redesign',
  action: () => Promise<T>, accepted: (result: T, props: Properties) => void = () => {}, properties: Record<string, unknown> = {},
): Promise<T> {
  const props = safeStudioProperties({ ...properties, operation_id: telemetryId() })
  const started = Date.now(), generation = workflow.generation()
  const enabled = workflow.active(generation)
  if (enabled) captureBusinessEvent(`${name}_requested`, props)
  try {
    const result = await action()
    if (enabled && workflow.active(generation)) {
      captureBusinessEvent(`${name}_accepted`, { ...props, request_duration_ms: Date.now() - started })
      try { accepted(result, props) } catch { /* local watch failures never change the API result */ }
    }
    return result
  } catch (error) {
    if (enabled && workflow.active(generation)) captureBusinessEvent(`${name}_request_failed`, {
      ...props, error_code: errorCode(error), request_duration_ms: Date.now() - started,
    })
    throw error
  }
}

export function trackQuickOutputPlatforms(properties: Record<string, unknown>) {
  captureBusinessEvent('studio_platforms_selected', safeStudioProperties(properties))
}

/** Enum/boolean summary of one output variant for delivery events; never titles, captions or names. */
export type VariantProperties = { strategy_id?: string; template?: string; packaging_style?: string; framing?: string; artifact_type?: 'video' | 'publish_kit'; outro_applied?: boolean }

/** Share intent only: which enum target, never the caption, title or link text. */
export function trackOutputShare(projectId: string, properties: { share_target: 'copy_caption' | 'use_case_discussion' } & VariantProperties) {
  captureBusinessEvent('studio_output_shared', safeStudioProperties({ ...workflow.context(projectId), ...properties }))
}

/** Anonymous three-level rating; free text is never collected. */
export function trackOutputRating(projectId: string, properties: { output_rating: 'ready' | 'needs_edit' | 'unusable' } & VariantProperties) {
  captureBusinessEvent('studio_output_rated', safeStudioProperties({ ...workflow.context(projectId), ...properties }))
}

/** Navigation intent only; no claim about successful disk writes. */
export function studioDownloadRequested(projectId?: string, jobId?: string, variant: VariantProperties = {}) {
  captureBusinessEvent('studio_download_requested', safeStudioProperties({ ...workflow.context(projectId, jobId), artifact_type: 'video', ...variant, download_mode: 'browser' }))
}

export async function observeStudioDownload<T>(action: () => Promise<T>, projectId?: string, jobId?: string, variant: VariantProperties = {}): Promise<T> {
  const generation = workflow.generation(), started = Date.now()
  const enabled = workflow.active(generation)
  const props = safeStudioProperties({ ...workflow.context(projectId, jobId), artifact_type: 'video', ...variant, operation_id: telemetryId(), download_mode: 'native' })
  const emit = (name: string, result: Properties = {}) => {
    if (enabled && workflow.active(generation)) captureBusinessEvent(name, { ...props, ...result })
  }
  emit('studio_download_requested')
  try {
    const result = await action()
    emit('studio_download_saved', { duration_ms: Date.now() - started })
    return result
  } catch (error) {
    emit('studio_download_failed', { duration_ms: Date.now() - started, error_code: errorCode(error) })
    throw error
  }
}

export function studioImportProperties(body: FormData): Record<string, unknown> {
  let source_type = 'file'
  const url = body.get?.('url')
  if (typeof url === 'string' && url) {
    source_type = 'other_url'
    try {
      const host = new URL(url).hostname.toLowerCase()
      if (host === 'youtu.be' || host === 'youtube.com' || host.endsWith('.youtube.com')) source_type = 'youtube'
      else if (host === 'b23.tv' || host === 'bilibili.com' || host.endsWith('.bilibili.com')) source_type = 'bilibili'
    } catch { /* invalid input remains an enum; URL is never captured */ }
  }
  return { material_origin: 'user', flow_id: telemetryId(), source_type, has_subtitle: !!body.get?.('subtitle'), goal: body.get?.('goal'), aspect: body.get?.('aspect') || 'auto', portrait_style: body.get?.('portrait_style') || 'auto', platform_count: Array.from(body.entries?.() || []).filter(([key]) => key === 'platforms').length,
    // Omitted means the backend's saved preference: do not claim it is enabled.
    brand_outro_enabled: body.get?.('brand_outro_enabled') === 'true' ? true : body.get?.('brand_outro_enabled') === 'false' ? false : undefined }
}

export function studioGoals(goals: string[]): Properties {
  return { goal_content: goals.includes('content'), goal_highlight: goals.includes('highlight'), goal_promo: goals.includes('promo') }
}

/** Called only for a submission enrolled in this mounted publish page. */
export function socialPublishObserved(generation: number, properties: Record<string, unknown>) {
  if (workflow.active(generation)) captureBusinessEvent('social_publish_finished', safeStudioProperties(properties))
}

export function socialPublishOutcome(status: string, scheduled: boolean, results: {success: boolean; skipped?: boolean; fallback_to_inbox?: boolean}[]): string {
  if (status === 'failed') return 'failed'
  const failed = results.some(r => !r.success && !r.skipped)
  const success = results.some(r => r.success && !r.skipped)
  if (failed) return success ? 'partial' : 'failed'
  if (scheduled) return 'scheduled'
  if (results.some(r => r.fallback_to_inbox)) return 'inbox'
  // A completed gateway with no platform evidence is not proof of publishing.
  return success ? 'completed' : 'unknown'
}

/** Reuse the snapshot already shown by the UI; quick confirmations must not
 * overwrite screening results before the background observer's next poll. */
export async function observeStudioWorkspace<T extends StudioSnapshot>(projectId: string, action: () => Promise<T>): Promise<T> {
  const generation = workflow.generation(), enabled = workflow.active(generation)
  const watches = enabled ? workflow.list().filter(watch => watch.kind.startsWith('studio-') && (watch.projectId || watch.id) === projectId) : []
  const snapshot = await action()
  if (enabled && workflow.active(generation)) workflow.rememberProject(projectId, snapshot as Record<string, unknown>)
  if (enabled && workflow.active(generation)) {
    try {
      for (const watch of watches) workflow.observeStudio(watch, snapshot)
    } catch { /* telemetry cannot prevent the editor from opening */ }
  }
  return snapshot
}
