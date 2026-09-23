import { captureBusinessEvent } from './posthog'
import { workflow } from './observer'
import { errorCode } from './workflow'

/** Only fixed event names, HTTP error categories and elapsed milliseconds leave the app.
 * No project/job/operation IDs, URLs, filenames, content or model output are captured. */
export async function observeStudioOperation<T>(
  name: 'studio_import' | 'studio_confirm' | 'studio_export',
  action: () => Promise<T>, accepted: (result: T) => void,
): Promise<T> {
  const started = Date.now(), generation = workflow.generation()
  const enabled = workflow.active(generation)
  if (enabled) captureBusinessEvent(`${name}_requested`, {})
  try {
    const result = await action()
    if (enabled && workflow.active(generation)) {
      captureBusinessEvent(`${name}_accepted`, { request_duration_ms: Date.now() - started })
      try { accepted(result) } catch { /* local watch failures never change the API result */ }
    }
    return result
  } catch (error) {
    if (enabled && workflow.active(generation)) captureBusinessEvent(`${name}_request_failed`, {
      error_code: errorCode(error), request_duration_ms: Date.now() - started,
    })
    throw error
  }
}

/** Navigation intent only; no claim about successful disk writes. */
export function studioDownloadRequested() {
  captureBusinessEvent('studio_download_requested', {})
}
