import type { OutputVariant } from './types'

const VARIANT_ID = /^[a-zA-Z0-9_-]{1,100}$/

export function outputVariantPublishPath(projectId: string, variant: OutputVariant) {
  const query = new URLSearchParams({ variant: variant.id, strategy: variant.strategy_id })
  return `/project/${projectId}/publish/studio-${variant.render_job_id}?${query}`
}

/** Which completed variant the publish page was opened for; only a bilibili variant goes straight to B站. */
export function outputVariantPublishTarget(search: string) {
  const params = new URLSearchParams(search)
  const id = params.get('variant') || ''
  if (!VARIANT_ID.test(id)) return { uploadPost: undefined, bilibili: undefined }
  return { uploadPost: id, bilibili: params.get('strategy') === 'bilibili' ? id : undefined }
}
