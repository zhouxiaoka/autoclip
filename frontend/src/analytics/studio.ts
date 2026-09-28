import { captureBusinessEvent } from './posthog'
import { workflow } from './observer'
import { errorCode, safeStudioProperties, type Properties, type StudioSnapshot } from './workflow'

/** Only allowlisted categories, booleans, counts and elapsed milliseconds leave the app.
 * No project/job/operation IDs, URLs, filenames, content or model output are captured. */
export async function observeStudioOperation<T>(
  name: 'studio_import' | 'studio_confirm' | 'studio_export' | 'studio_rescreen' | 'studio_plan_update' | 'studio_draft_create' | 'studio_draft_save' | 'studio_draft_duplicate' | 'studio_rewrite' | 'studio_analysis_preferences' | 'vision_provider_test' | 'vision_provider_save' | 'social_publish',
  action: () => Promise<T>, accepted: (result: T) => void = () => {}, properties: Record<string, unknown> = {},
): Promise<T> {
  const props = safeStudioProperties(properties)
  const started = Date.now(), generation = workflow.generation()
  const enabled = workflow.active(generation)
  if (enabled) captureBusinessEvent(`${name}_requested`, props)
  try {
    const result = await action()
    if (enabled && workflow.active(generation)) {
      captureBusinessEvent(`${name}_accepted`, { ...props, request_duration_ms: Date.now() - started })
      try { accepted(result) } catch { /* local watch failures never change the API result */ }
    }
    return result
  } catch (error) {
    if (enabled && workflow.active(generation)) captureBusinessEvent(`${name}_request_failed`, {
      ...props, error_code: errorCode(error), request_duration_ms: Date.now() - started,
    })
    throw error
  }
}

/** Navigation intent only; no claim about successful disk writes. */
export function studioDownloadRequested() {
  captureBusinessEvent('studio_download_requested', safeStudioProperties({ download_mode: 'browser' }))
}

export async function observeStudioDownload<T>(action: () => Promise<T>): Promise<T> {
  const generation = workflow.generation(), started = Date.now()
  const enabled = workflow.active(generation)
  const props = safeStudioProperties({ download_mode: 'native' })
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
  return { source_type, has_subtitle: !!body.get?.('subtitle'), goal: body.get?.('goal'), aspect: body.get?.('aspect') || 'auto' }
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
  if (enabled && workflow.active(generation)) {
    try {
      for (const watch of watches) workflow.observeStudio(watch, snapshot)
    } catch { /* telemetry cannot prevent the editor from opening */ }
  }
  return snapshot
}
