import type { Connection, ModelEntry, ModelSettings } from './modelSettingsApi'
import { getProvider } from './providerPresets'

// Families tried in order when a provider has no curated candidates (gateways like 88API).
// For each family the newest ID (numeric sort, descending) wins, so a long gateway list
// starts with a handful of sensible picks instead of everything or nothing.
const LANGUAGE_FAMILIES: RegExp[] = [
  /^claude-sonnet/i, /^claude-opus/i, /^gpt-\d(?!.*(codex|image|audio|realtime|mini|nano))/i,
  /^gemini-[\d.]+-pro(?!.*image)/i, /^gemini-[\d.]+-flash(?!.*(lite|image))/i,
  /^deepseek/i, /^qwen/i, /^glm/i, /^kimi/i,
]
const LANGUAGE_LIMIT = 6
const IMAGE_LIMIT = 2

const newestFirst = (a: string, b: string) => b.localeCompare(a, undefined, { numeric: true, sensitivity: 'base' })

function pickFamilies(ids: string[], families: RegExp[], limit: number): string[] {
  const out: string[] = []
  for (const family of families) {
    if (out.length >= limit) break
    const match = ids.filter(id => family.test(id)).sort(newestFirst)[0]
    if (match && !out.includes(match)) out.push(match)
  }
  return out
}

function assignedModels(settings: ModelSettings, connectionId: string): string[] {
  const bindings = [settings.analysis, settings.vision, settings.cover, settings.transcription] as Array<{ connection_id?: string; model?: string } | null | undefined>
  return bindings.filter(b => b?.connection_id === connectionId && b.model).map(b => b!.model!)
}

/** Default enabled set for a connection whose user never edited visibility. */
export function recommendedModelIds(settings: ModelSettings, connection: Connection, models: ModelEntry[]): string[] {
  const preset = getProvider(connection.catalog_provider_id || connection.provider)
  const candidates = preset?.candidates
  const ids = new Set(models.map(m => m.id))
  const language = models.filter(m => m.analysis).map(m => m.id)
  const image = models.filter(m => m.image).map(m => m.id)
  const selectableAsr = models.filter(m => m.asr && m.asr_supported && !m.asr_preview).map(m => m.id)
  const fromCatalog = (list?: string[]) => (list || []).filter(id => ids.has(id))
  const pickedLanguage = [...fromCatalog(candidates?.analysis), ...fromCatalog(candidates?.vision)]
  const pickedImage = fromCatalog(candidates?.image)
  const pickedAsr = fromCatalog(candidates?.asr).filter(id => selectableAsr.includes(id))
  const result = [
    ...assignedModels(settings, connection.id).filter(id => ids.has(id)),
    ...(pickedLanguage.length ? pickedLanguage : pickFamilies(language, LANGUAGE_FAMILIES, LANGUAGE_LIMIT)),
    ...(pickedImage.length ? pickedImage : image.slice(0, IMAGE_LIMIT)),
    ...(pickedAsr.length ? pickedAsr : selectableAsr.slice(0, 1)),
  ]
  if (!result.length && language.length) result.push(language[0])
  return [...new Set(result)]
}

/** Effective enabled IDs: the user's explicit list, else the recommendation. */
export function enabledModelIds(settings: ModelSettings, connection: Connection, models: ModelEntry[]): Set<string> {
  return new Set(Array.isArray(connection.enabled_model_ids) ? connection.enabled_model_ids : recommendedModelIds(settings, connection, models))
}
