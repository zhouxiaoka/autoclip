/**
 * Draft + constraints for a user-added OpenAI-compatible provider.
 * Protocol is fixed; model attributes follow the settings purpose rules.
 */
import { cleanupBaseUrl, normalizeProviderBaseUrl } from './providerUrl'
import type { Connection, ModelEntry, ModelList, ModelSettings } from './modelSettingsApi'
import { cleanBinding } from './modelSettingsLogic'
import { isConsoleHost } from './providerAccess'

export const CUSTOM_PROTOCOL = 'openai_compatible' as const
export type CustomProtocol = typeof CUSTOM_PROTOCOL

export const MODEL_TYPES = ['language', 'asr', 'tts', 'image', 'music', 'video'] as const
export type ModelType = (typeof MODEL_TYPES)[number]

export const SCENARIOS = ['analysis', 'vision', 'transcription', 'cover'] as const
export type Scenario = (typeof SCENARIOS)[number]

export type CustomModelOffer = {
  id: string
  display_name: string
  types: ModelType[]
  vision: boolean
  scenarios: Scenario[]
  enabled: boolean
}

export type CustomProviderDraft = {
  name: string
  protocol: CustomProtocol
  base_url: string
  api_key: string
  models: CustomModelOffer[]
}

export type DraftIssue = 'name' | 'url' | 'models' | 'model_id' | 'duplicate'

export const emptyDraft = (): CustomProviderDraft => ({
  name: '',
  protocol: CUSTOM_PROTOCOL,
  base_url: '',
  api_key: '',
  models: [],
})

export const emptyOffer = (id: string): CustomModelOffer => constrainOffer({
  id: id.trim(),
  display_name: '',
  types: ['language'],
  vision: false,
  scenarios: ['analysis'],
  enabled: true,
})

export function scenarioAllowed(types: readonly ModelType[], vision: boolean, scenario: Scenario): boolean {
  if (scenario === 'transcription') return types.includes('asr')
  if (scenario === 'cover') return types.includes('image')
  if (scenario === 'analysis') return types.includes('language')
  return types.includes('language') && vision
}

export function constrainOffer(offer: CustomModelOffer): CustomModelOffer {
  const types = unique<ModelType>(offer.types.length ? offer.types : ['language'])
  const vision = types.includes('language') && offer.vision
  const scenarios = unique<Scenario>(offer.scenarios.filter(scenario => scenarioAllowed(types, vision, scenario)))
  return { ...offer, id: offer.id.trim(), display_name: offer.display_name.trim(), types, vision, scenarios }
}

export function offerFromEntry(entry: ModelEntry): CustomModelOffer {
  const types: ModelType[] = []
  if (entry.image) types.push('image')
  if (entry.asr) types.push('asr')
  if (entry.analysis || (!entry.image && !entry.asr)) types.push('language')
  const vision = types.includes('language') && entry.capability === 'multimodal'
  const scenarios: Scenario[] = []
  if (types.includes('language')) scenarios.push('analysis')
  if (vision) scenarios.push('vision')
  if (types.includes('asr')) scenarios.push('transcription')
  if (types.includes('image')) scenarios.push('cover')
  return constrainOffer({
    id: entry.id,
    display_name: '',
    types,
    vision,
    scenarios,
    enabled: false,
  })
}

export function mergeDiscovered(draft: CustomProviderDraft, entries: ModelEntry[]): CustomProviderDraft {
  const byId = new Map(draft.models.map(model => [model.id, model]))
  for (const entry of entries) {
    if (!entry.id || byId.has(entry.id)) continue
    byId.set(entry.id, offerFromEntry(entry))
  }
  return { ...draft, models: Array.from(byId.values()) }
}

export function mergeFetched(draft: CustomProviderDraft, ids: string[]): CustomProviderDraft {
  return mergeDiscovered(draft, ids.filter(Boolean).map(id => ({
    id, capability: null, analysis: true, image: false,
  })))
}

/** Custom offers win on id clash so a live /models refresh cannot drop user attributes. */
export function mergeCustomList(connection: Connection, live?: ModelList | null): ModelList {
  const custom = listFromOffers(connection.custom_models || [], live?.models)
  if (!live) return custom
  if (!custom.models.length) return live
  const byId = new Map(live.models.map(model => [model.id, model]))
  for (const entry of custom.models) byId.set(entry.id, entry)
  return { ...live, models: Array.from(byId.values()) }
}

export function addManualModel(draft: CustomProviderDraft, rawId: string): { draft: CustomProviderDraft; issue?: DraftIssue } {
  const id = rawId.trim()
  if (!id) return { draft, issue: 'model_id' }
  if (draft.models.some(model => model.id === id)) return { draft, issue: 'duplicate' }
  return { draft: { ...draft, models: [...draft.models, emptyOffer(id)] } }
}

export function toggleModel(draft: CustomProviderDraft, id: string, enabled: boolean): CustomProviderDraft {
  return {
    ...draft,
    models: draft.models.map(model => model.id === id ? { ...model, enabled } : model),
  }
}

export function editModel(draft: CustomProviderDraft, id: string, patch: Partial<CustomModelOffer>): CustomProviderDraft {
  return {
    ...draft,
    models: draft.models.map(model => model.id === id ? constrainOffer({ ...model, ...patch, id: model.id }) : model),
  }
}

export function visibleModels(draft: CustomProviderDraft, search: string): CustomModelOffer[] {
  const query = search.trim().toLowerCase()
  if (!query) return draft.models
  return draft.models.filter(model => `${model.id} ${model.display_name}`.toLowerCase().includes(query))
}

export function normalizedDraftUrl(url: string): string {
  return normalizeProviderBaseUrl(url, 'compatible')
}

function urlLooksBlocked(value: string): boolean {
  try {
    const parsed = new URL(value)
    if ((parsed.protocol !== 'http:' && parsed.protocol !== 'https:') || !parsed.hostname) return true
    if (parsed.username || parsed.password) return true
    return isConsoleHost(parsed.hostname)
  } catch {
    return true
  }
}

export function draftUrlIssue(url: string): 'empty' | 'invalid' | null {
  const stripped = cleanupBaseUrl(url)
  if (!stripped) return 'empty'
  const cleaned = normalizedDraftUrl(url)
  if (!cleaned) return 'empty'
  if (urlLooksBlocked(stripped) || urlLooksBlocked(cleaned)) return 'invalid'
  return null
}

export function draftIssue(draft: CustomProviderDraft): Exclude<DraftIssue, 'model_id' | 'duplicate'> | null {
  if (!draft.name.trim()) return 'name'
  if (draftUrlIssue(draft.base_url)) return 'url'
  if (!draft.models.some(model => model.enabled && model.id.trim())) return 'models'
  return null
}

export function enabledOffers(draft: CustomProviderDraft): CustomModelOffer[] {
  return draft.models.filter(model => model.enabled && model.id.trim()).map(constrainOffer)
}

export function toConnection(draft: CustomProviderDraft, id: string = crypto.randomUUID()): Connection {
  const key = draft.api_key.trim()
  return {
    id,
    name: draft.name.trim().slice(0, 100),
    provider: 'compatible',
    base_url: normalizedDraftUrl(draft.base_url),
    base_url_source: 'user',
    api_key: key,
    has_key: !!key,
    image_api: 'auto',
    image_base_url: '',
    custom_models: enabledOffers(draft),
  }
}

export function listFromOffers(offers: CustomModelOffer[], verified: ModelEntry[] = []): ModelList {
  return {
    models: offers.filter(offer => offer.enabled).map(offer => ({
      id: offer.id,
      capability: offer.vision ? 'multimodal' : offer.types.includes('language') ? 'text' : null,
      analysis: offer.scenarios.includes('analysis') || offer.types.includes('language'),
      image: offer.types.includes('image') || offer.scenarios.includes('cover'),
      asr: offer.types.includes('asr') || offer.scenarios.includes('transcription'),
      // Timestamp support belongs to the backend asr_model_catalog adapter.
      asr_supported: verified.find(model => model.id === offer.id)?.asr_supported ?? false,
      asr_note: verified.find(model => model.id === offer.id)?.asr_note,
    })),
    source: 'live',
    preview: false,
    updated_at: Date.now(),
  }
}

export function firstBoundModel(draft: CustomProviderDraft): CustomModelOffer | undefined {
  const enabled = enabledOffers(draft)
  return enabled.find(model => model.scenarios.includes('analysis') || model.types.includes('language'))
}

/** Append a custom connection. Bind analysis only when the document has none yet. */
export function applyCustomProvider(settings: ModelSettings, draft: CustomProviderDraft, id?: string): ModelSettings {
  const connection = toConnection(draft, id)
  const next: ModelSettings = { ...settings, connections: [...settings.connections, connection] }
  if (next.analysis) return next
  const model = firstBoundModel(draft)
  if (!model) return next
  return {
    ...next,
    analysis: { ...cleanBinding(connection.id), model: model.id, capability: model.vision ? 'multimodal' : 'auto', model_source: 'user' },
  }
}

function unique<T>(items: readonly T[]): T[] {
  const seen = new Set<T>()
  const out: T[] = []
  for (const item of items) {
    if (seen.has(item)) continue
    seen.add(item)
    out.push(item)
  }
  return out
}
