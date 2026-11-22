import type { VariantProperties } from '../../analytics/studio'
import type { Draft, OutputVariant, RenderJob } from './types'

const VARIANT_ID = /^[a-zA-Z0-9_-]{1,100}$/

export function studioPublishPreviewPath(projectId: string, draftId: string, jobId: string, variantId?: string) {
  const query = new URLSearchParams({ publish: jobId })
  if (variantId) query.set('variant', variantId)
  return `/project/${projectId}/studio/${draftId}?${query}`
}

export function outputVariantPublishQuery(variant: OutputVariant) {
  return new URLSearchParams({ variant: variant.id, strategy: variant.strategy_id }).toString()
}

/** Which completed variant the publish page was opened for; only a bilibili variant goes straight to B站. */
export function outputVariantPublishTarget(search: string) {
  const params = new URLSearchParams(search)
  const id = params.get('variant') || ''
  if (!VARIANT_ID.test(id)) return { uploadPost: undefined, bilibili: undefined }
  return { uploadPost: id, bilibili: params.get('strategy') === 'bilibili' ? id : undefined }
}

export function outputAnalytics(variant: OutputVariant, draft?: Draft, job?: RenderJob, recommendation?: Pick<VariantProperties, 'recommended_template' | 'accepted_recommendation'>): VariantProperties {
  const packaging = draft?.packaging
  const rendered = job?.result?.template_render?.template
  const template = rendered === 'editorial' || rendered === 'street' || rendered === 'news' || rendered === 'cinema' || rendered === 'classic' ? rendered : packaging?.template
  return {
    strategy_id: variant.strategy_id, framing: variant.framing, template,
    packaging_style: packaging ? packaging.style || (packaging.template === 'podcast_en' ? 'pop' : 'classic') : undefined,
    outro_applied: job?.result?.outro_applied,
    recommended_template: recommendation?.recommended_template,
    accepted_recommendation: recommendation?.accepted_recommendation,
  }
}
