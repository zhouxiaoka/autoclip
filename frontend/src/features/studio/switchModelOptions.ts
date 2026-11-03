/** X2: connections eligible for 「换模型重试」 (configured + F2 try-run ok / ready). */
import { qualityFor, type SuccessTier } from '../settings/providerQuality'
import { connectionReady } from '../settings/modelSettingsLogic'
import { getProvider } from '../settings/providerPresets'
import { isKnownWeakLocalTimelineModel } from '../settings/weakLocalTimeline'
import type { Connection, ModelSettings } from '../settings/modelSettingsApi'

export type SwitchModelOption = {
  connectionId: string
  model: string
  displayName: string
  providerId: string
  success_tier?: SuccessTier
  success_rate?: number
}

const LOCAL = new Set(['ollama', 'lmstudio'])

function isCloud(connection: Connection): boolean {
  const id = (connection.provider || '').trim().toLowerCase()
  if (LOCAL.has(id)) return false
  if ((id === 'compatible' || id === 'openai' || id === 'other')
    && isKnownWeakLocalTimelineModel(id, 'qwen2.5:7b', connection.base_url)) return false
  return true
}

function modelsOf(connection: Connection): string[] {
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

/** Passed F2 try-run (validation ok) or a ready local connection. */
export function connectionUsableForSwitch(connection: Connection): boolean {
  if (!connectionReady(connection)) return false
  if (isCloud(connection)) return connection.validation_status === 'ok'
  return true
}

/** Count of usable analysis connections (for failureAction.connectionCount). */
export function usableConnectionCount(settings?: ModelSettings | null): number {
  const seen = new Set<string>()
  for (const connection of settings?.connections || []) {
    if (!connectionUsableForSwitch(connection)) continue
    seen.add(connection.id)
  }
  return seen.size
}

/** Provider id of the current analysis binding (for recharge routing). */
export function analysisProviderId(settings?: ModelSettings | null): string | null {
  const current = settings?.analysis
  if (!current?.connection_id) return null
  const connection = (settings?.connections || []).find(c => c.id === current.connection_id)
  if (!connection) return null
  return (connection.catalog_provider_id || connection.provider || '').trim().toLowerCase() || null
}

/** Options for SwitchModelDialog: usable connections × models, sorted by F1 success_rate desc. */
export function listSwitchModelOptions(
  settings?: ModelSettings | null,
  exclude?: { connectionId?: string | null; model?: string | null },
): SwitchModelOption[] {
  const out: SwitchModelOption[] = []
  for (const connection of settings?.connections || []) {
    if (!connectionUsableForSwitch(connection)) continue
    const cloud = isCloud(connection)
    const providerId = (connection.catalog_provider_id || connection.provider || '').trim().toLowerCase()
    const quality = qualityFor(providerId)
    for (const model of modelsOf(connection)) {
      if (/embed|whisper|rerank/i.test(model)) continue
      if (exclude?.connectionId && exclude?.model
        && connection.id === exclude.connectionId && model === exclude.model) continue
      if (isKnownWeakLocalTimelineModel(connection.provider, model, connection.base_url)) continue
      out.push({
        connectionId: connection.id,
        model,
        displayName: displayName(connection, model, cloud),
        providerId,
        success_tier: quality?.success_tier,
        success_rate: quality?.success_rate,
      })
    }
  }
  out.sort((a, b) => (b.success_rate ?? -1) - (a.success_rate ?? -1))
  return out
}

export function defaultSwitchOption(options: SwitchModelOption[]): SwitchModelOption | null {
  return options[0] || null
}
