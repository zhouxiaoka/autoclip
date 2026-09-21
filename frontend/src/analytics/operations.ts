import { captureBusinessEvent } from './posthog'
import { workflow } from './observer'
import { errorCode, type Properties } from './workflow'

/** Track an attempt, not just a click. Instrumentation must never alter its result. */
export async function observeOperation<T>(
  name: string, properties: Properties, action: () => Promise<T>,
  onAccepted?: (result: T, startedAt: number, properties: Properties) => void,
): Promise<T> {
  const startedAt = Date.now()
  const generation = workflow.generation()
  const enabledAtStart = workflow.active(generation)
  const operationId = globalThis.crypto?.randomUUID?.() ?? `${startedAt}-${Math.random().toString(36).slice(2)}`
  const props = { ...properties, operation_id: operationId }
  if (enabledAtStart) captureBusinessEvent(`${name}_requested`, props)
  try {
    const result = await action()
    if (enabledAtStart && workflow.active(generation)) {
      captureBusinessEvent(`${name}_accepted`, { ...props, request_duration_ms: Date.now() - startedAt })
      try { onAccepted?.(result, startedAt, props) } catch { /* telemetry must not change a successful API result */ }
    }
    return result
  } catch (error) {
    if (enabledAtStart && workflow.active(generation)) captureBusinessEvent(`${name}_request_failed`, {
      ...props, error_code: errorCode(error), request_duration_ms: Date.now() - startedAt,
    })
    throw error
  }
}

/** Received bytes is measurable; the browser's save-to-disk outcome is not. */
export async function observeDownload<T extends Blob>(properties: Properties, action: () => Promise<T>): Promise<T> {
  return observeOperation('media_download', properties, async () => {
    const blob = await action()
    if (!(blob instanceof Blob) || blob.size === 0) throw new Error('Empty media response')
    return blob
  }, (blob, _startedAt, props) => { captureBusinessEvent('media_download_received', { ...props, size_bytes: blob.size }) })
}

export async function observeMediaResponse<T extends { data: Blob }>(properties: Properties, action: () => Promise<T>): Promise<T> {
  return observeOperation('media_download', properties, async () => {
    const response = await action()
    if (!(response.data instanceof Blob) || response.data.size === 0) throw new Error('Empty media response')
    return response
  }, (response, _startedAt, props) => { captureBusinessEvent('media_download_received', { ...props, size_bytes: response.data.size }) })
}
