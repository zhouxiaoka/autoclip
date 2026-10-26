/**
 * One replacement for a weak local timeline model (#428).
 * A connected cloud model wins. Otherwise the smallest larger local model
 * the user already enabled. Never invents a sponsor that is not connected.
 */
import { isKnownWeakLocalTimelineModel } from './weakLocalTimeline'
import { connectionReady } from './modelSettingsLogic'
import { getProvider } from './providerPresets'
import type { Connection, ModelSettings } from './modelSettingsApi'

export type TimelineReplacement = {
  connectionId: string
  model: string
  displayName: string
}

const LOCAL_PROVIDERS = new Set(['ollama', 'lmstudio'])

function billions(model: string): number | null {
  const sizes = [...model.toLowerCase().matchAll(/(?:^|[^0-9a-z])(\d+(?:\.\d+)?)b(?=[^0-9a-z]|$)/g)]
  return sizes.length ? Number(sizes[sizes.length - 1][1]) : null
}

function isCloud(connection: Connection): boolean {
  const id = (connection.provider || '').trim().toLowerCase()
  if (LOCAL_PROVIDERS.has(id)) return false
  if ((id === 'compatible' || id === 'openai' || id === 'other') && isKnownWeakLocalTimelineModel(id, 'qwen2.5:7b', connection.base_url)) return false
  return true
}

function choices(connection: Connection): string[] {
  if (Array.isArray(connection.enabled_model_ids) && connection.enabled_model_ids.length) {
    return connection.enabled_model_ids.filter(id => typeof id === 'string' && id.trim())
  }
  const preset = getProvider(connection.catalog_provider_id || connection.provider)
  const listed = (preset?.candidates?.analysis || []).filter(Boolean)
  if (listed.length) return listed
  return preset?.default_model ? [preset.default_model] : []
}

function displayName(connection: Connection, model: string, cloud: boolean): string {
  if (!cloud) return model
  return getProvider(connection.catalog_provider_id || connection.provider)?.short_name || connection.name || model
}

/** The one model to offer on the home failure card, or null when nothing else is usable. */
export function recommendTimelineReplacement(settings?: ModelSettings | null): TimelineReplacement | null {
  const current = settings?.analysis
  if (!current?.model || !settings) return null
  const currentSize = billions(current.model)
  const clouds: TimelineReplacement[] = []
  const locals: Array<TimelineReplacement & { size: number }> = []
  for (const connection of settings.connections || []) {
    if (!connectionReady(connection)) continue
    const cloud = isCloud(connection)
    if (cloud && connection.validation_status !== 'ok') continue
    for (const model of choices(connection)) {
      if (/embed|whisper|rerank/i.test(model)) continue
      if (connection.id === current.connection_id && model === current.model) continue
      if (isKnownWeakLocalTimelineModel(connection.provider, model, connection.base_url)) continue
      const item = { connectionId: connection.id, model, displayName: displayName(connection, model, cloud) }
      if (cloud) {
        clouds.push(item)
        continue
      }
      const size = billions(model)
      if (size == null) continue
      if (currentSize != null ? size <= currentSize : size <= 8) continue
      locals.push({ ...item, size })
    }
  }
  if (clouds.length) return clouds[0]
  locals.sort((a, b) => a.size - b.size)
  return locals[0] ? { connectionId: locals[0].connectionId, model: locals[0].model, displayName: locals[0].displayName } : null
}
