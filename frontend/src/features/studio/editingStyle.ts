export const HTML_TEMPLATE_CHOICES = ['editorial', 'street', 'classic'] as const
export type HtmlTemplateChoice = (typeof HTML_TEMPLATE_CHOICES)[number]
export type EditingStyle = HtmlTemplateChoice
export const DEFAULT_HTML_TEMPLATE: HtmlTemplateChoice = 'editorial'

export const REASON_CODES = ['seated_interview', 'street_quick', 'speech', 'default', 'timeout'] as const
export type ReasonCode = (typeof REASON_CODES)[number]

export type StyleSignals = {
  scene: 'seated_interview' | 'street' | 'speech' | 'unknown'
  people: 'solo' | 'duo' | 'group' | 'unknown'
  pace: 'calm' | 'fast' | 'unknown'
  captions: 'bilingual' | 'zh' | 'en' | 'none' | 'unknown'
  duration_bucket: 'short' | 'medium' | 'long' | 'unknown'
}

export type StyleRecommendation = {
  template: EditingStyle
  reason_code: ReasonCode
  signals: StyleSignals
}

const EMPTY_SIGNALS: StyleSignals = {
  scene: 'unknown', people: 'unknown', pace: 'unknown', captions: 'unknown', duration_bucket: 'unknown',
}

export function chosenTemplate(value: string | undefined): HtmlTemplateChoice {
  return value === 'street' || value === 'classic' ? value : DEFAULT_HTML_TEMPLATE
}

/** Import fields for the HTML template. The flag-off path sends nothing. */
export function templateImportFields(enabled: boolean, value: string | undefined, recommended?: string | null): { html_template?: HtmlTemplateChoice; recommended_template?: HtmlTemplateChoice } {
  if (!enabled) return {}
  const html_template = chosenTemplate(value)
  const recommended_template = recommended === 'editorial' || recommended === 'street' || recommended === 'classic' ? recommended : undefined
  return recommended_template ? { html_template, recommended_template } : { html_template }
}

export function isEditingStyle(value: unknown): value is EditingStyle {
  return value === 'editorial' || value === 'street' || value === 'classic'
}

function oneOf<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
  return typeof value === 'string' && (allowed as readonly string[]).includes(value) ? value as T : fallback
}

/** Drop anything that is not an enum. A bad payload becomes the editorial default. */
export function normalizeRecommendation(raw: unknown): StyleRecommendation | null {
  if (!raw || typeof raw !== 'object') return null
  const body = raw as Record<string, unknown>
  const signals = body.signals && typeof body.signals === 'object' ? body.signals as Record<string, unknown> : {}
  return {
    template: oneOf(body.template, HTML_TEMPLATE_CHOICES, 'editorial'),
    reason_code: oneOf(body.reason_code, REASON_CODES, 'default'),
    signals: {
      scene: oneOf(signals.scene, ['seated_interview', 'street', 'speech', 'unknown'] as const, 'unknown'),
      people: oneOf(signals.people, ['solo', 'duo', 'group', 'unknown'] as const, 'unknown'),
      pace: oneOf(signals.pace, ['calm', 'fast', 'unknown'] as const, 'unknown'),
      captions: oneOf(signals.captions, ['bilingual', 'zh', 'en', 'none', 'unknown'] as const, 'unknown'),
      duration_bucket: oneOf(signals.duration_bucket, ['short', 'medium', 'long', 'unknown'] as const, 'unknown'),
    },
  }
}

export function recommendationTimedOut(): StyleRecommendation {
  return { template: 'editorial', reason_code: 'timeout', signals: { ...EMPTY_SIGNALS } }
}

export function recommendationFailed(): StyleRecommendation {
  return { template: 'editorial', reason_code: 'default', signals: { ...EMPTY_SIGNALS } }
}

/** A manual choice wins. Otherwise the recommendation replaces the preselected style. */
export function selectionAfterRecommendation(manual: EditingStyle | null, recommended: EditingStyle | null, current: EditingStyle): { selected: EditingStyle; apply: boolean } {
  if (manual) return { selected: manual, apply: false }
  const selected = recommended || current
  return { selected, apply: Boolean(recommended) && selected !== current }
}

export function degradeFromEnvironment(cores: number | undefined, backdrop: boolean, reducedTransparency: boolean): boolean {
  if (reducedTransparency || !backdrop) return true
  return typeof cores === 'number' && cores > 0 && cores <= 2
}

export function supportsBackdrop(): boolean {
  return typeof CSS !== 'undefined' && typeof CSS.supports === 'function' && (CSS.supports('backdrop-filter', 'blur(1px)') || CSS.supports('-webkit-backdrop-filter', 'blur(1px)'))
}

export function intelMacFromHints(platform: string, architecture: string): boolean {
  if (!/mac/i.test(platform)) return false
  if (!architecture || /arm/i.test(architecture)) return false
  return /x86|x64|ia32|amd64/i.test(architecture)
}

export function sceneKey(scene: StyleSignals['scene']): string {
  return `editing_style.scene.${scene}`
}
export function paceKey(pace: StyleSignals['pace']): string {
  return `editing_style.pace.${pace}`
}
export function captionsKey(captions: StyleSignals['captions']): string {
  return `editing_style.captions.${captions}`
}
export function durationKey(bucket: StyleSignals['duration_bucket']): string {
  return `editing_style.duration.${bucket}`
}

export const PREVIEW_SECONDS = 2.5
export const RECOMMEND_TIMEOUT_MS = 2000
