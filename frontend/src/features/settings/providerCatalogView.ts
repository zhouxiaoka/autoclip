/**
 * Settings catalog (U1): group, search, capability filter, and connection matching.
 * Driven by backend/presets/provider_presets.json. No React, no telemetry payloads.
 */
import { PROVIDERS, type ProviderKey } from './providers'
import { getCatalog, getProvider, resolveProviderId, type ProviderGroupId, type ProviderPreset } from './providerPresets'
import { cleanBinding, newConnection, presetKey, endpointProviderReady } from './modelSettingsLogic'
import type { Connection, ModelSettings } from './modelSettingsApi'
import { syncFollowingCover } from './modelDefaults'

export type CapabilityFilter = 'all' | 'language' | 'asr' | 'tts' | 'image' | 'music' | 'video'
export type CatalogConnectKind = 'legacy' | 'local_asr' | 'compatible' | 'guide' | 'needs_endpoint'
export type LocalAsrId = 'whisper' | 'sensevoice'
export type LocalAsrReady = { whisper?: boolean; sensevoice?: boolean }

export const CAPABILITY_FILTERS: CapabilityFilter[] = ['all', 'language', 'asr', 'tts', 'image', 'music', 'video']
export const CATALOG_GROUPS: ProviderGroupId[] = ['recommended', 'popular', 'local', 'more']

const LEGACY_IDS = new Set<string>([
  'dashscope', 'openai', 'infistar', 'api88', 'apimart', 'gemini', 'deepseek',
  'seed', 'kimi', 'glm', 'grok', 'ollama', 'lmstudio',
])
const OPENAI_LIKE = new Set(['openai-completions', 'openai-responses'])

export function catalogProviders(): ProviderPreset[] {
  return Object.values(getCatalog().providers)
}

export function displayNameOf(preset: ProviderPreset): string {
  return preset.ui_name || preset.display_name
}

export function connectKind(preset: ProviderPreset): CatalogConnectKind {
  if (preset.id === 'whisper' || preset.id === 'sensevoice') return 'local_asr'
  if (LEGACY_IDS.has(preset.id)) return 'legacy'
  if (!preset.base_url.trim()) return OPENAI_LIKE.has(preset.protocol) ? 'needs_endpoint' : 'guide'
  if (OPENAI_LIKE.has(preset.protocol)) return 'compatible'
  return 'guide'
}

/** Eligible for the live picker / as the current analysis default. Empty-URL presets are not. */
export function isLiveConnectable(preset: ProviderPreset): boolean {
  const kind = connectKind(preset)
  return kind === 'legacy' || kind === 'compatible' || kind === 'local_asr'
}

export function isLegacyProviderId(id: string): id is ProviderKey {
  return LEGACY_IDS.has(id) && id in PROVIDERS
}

/** Hostname only. Never return the original URL (telemetry / logs must not store it). */
export function catalogHost(url?: string): string {
  try {
    return new URL((url || '').trim()).hostname.toLowerCase().replace(/^\[|\]$/g, '')
  } catch {
    return ''
  }
}

export function matchesQuery(preset: ProviderPreset, query: string): boolean {
  const needle = query.trim().toLowerCase()
  if (!needle) return true
  return [preset.display_name, preset.ui_name, preset.short_name, preset.id]
    .some(value => value.toLowerCase().includes(needle))
}

export function matchesCapability(preset: ProviderPreset, filter: CapabilityFilter): boolean {
  return filter === 'all' || preset.capabilities.includes(filter)
}

export function filterCatalog(query: string, filter: CapabilityFilter): ProviderPreset[] {
  return catalogProviders().filter(preset => matchesQuery(preset, query) && matchesCapability(preset, filter))
}

export function groupCatalog(presets: ProviderPreset[]): Record<ProviderGroupId, ProviderPreset[]> {
  const groups: Record<ProviderGroupId, ProviderPreset[]> = { recommended: [], popular: [], local: [], more: [] }
  for (const preset of presets) groups[preset.group].push(preset)
  return groups
}

export function shouldExpandMore(query: string, filter: CapabilityFilter, moreCount: number): boolean {
  return moreCount > 0 && (!!query.trim() || filter !== 'all')
}

export function initialLetter(preset: ProviderPreset): string {
  const name = (preset.short_name || preset.display_name).trim()
  return (name.charAt(0) || '?').toUpperCase()
}

export function findCatalogConnection(settings: ModelSettings, preset: ProviderPreset): Connection | undefined {
  if (preset.id === 'whisper' || preset.id === 'sensevoice') return undefined
  const byId = settings.connections.find(connection => {
    const resolved = resolveProviderId(connection.catalog_provider_id || connection.provider) || connection.provider
    if (resolved === preset.id) return preset.id !== 'openai' || presetKey(connection) === 'openai'
    return false
  })
  if (byId) return byId
  if (preset.id === 'openai') return settings.connections.find(connection => presetKey(connection) === 'openai')
  const host = catalogHost(preset.base_url)
  if (!host) return undefined
  return settings.connections.find(connection => (
    (connection.provider === 'compatible' || presetKey(connection) === 'compatible')
    && catalogHost(connection.base_url) === host
  ))
}

export function whisperAsrReady(
  runtime?: { status?: string } | null,
  models?: Array<{ name: string; status: string }> | null,
  selectedModel?: string,
): boolean {
  const name = selectedModel || 'base'
  const model = (models || []).find(row => row.name === name)
  return runtime?.status === 'installed' && model?.status === 'downloaded'
}

export function sensevoiceAsrReady(status?: { status?: string } | null): boolean {
  return status?.status === 'ready'
}

/** Credentials (or a keyless connection) are configuration, not proof of connectivity. */
export function isCatalogConfigured(settings: ModelSettings, preset: ProviderPreset): boolean {
  const connection = findCatalogConnection(settings, preset)
  if (!connection || !endpointProviderReady(connection)) return false
  if (!preset.base_url && preset.protocol !== 'local') return true
  if (preset.auth === 'none') return true
  return !!(connection.api_key?.trim() || connection.has_key)
}

export function isCatalogConnected(settings: ModelSettings, preset: ProviderPreset, asrReady: LocalAsrReady = {}): boolean {
  // Readiness describes the installed engine, independently of the current ASR selection.
  if (preset.id === 'whisper') return !!asrReady.whisper
  if (preset.id === 'sensevoice') return !!asrReady.sensevoice
  return isCatalogConfigured(settings, preset) && findCatalogConnection(settings, preset)?.validation_status === 'ok'
}

export function selectLocalAsr(settings: ModelSettings, id: LocalAsrId, model?: string): ModelSettings {
  if (id === 'sensevoice') return { ...settings, transcription: { provider: 'sensevoice_local', model: 'SenseVoiceSmall' } }
  const current = settings.transcription?.provider === 'whisper_local' ? settings.transcription.model : 'base'
  return { ...settings, transcription: { provider: 'whisper_local', model: model || current || 'base' } }
}

/** In-memory form row. Opening a card must not write this into settings. */
export function catalogDraftConnection(preset: ProviderPreset, id = `draft:${preset.id}`): Connection | undefined {
  const kind = connectKind(preset)
  if (kind === 'local_asr' || (kind === 'guide' && preset.base_url)) return undefined
  if (kind === 'legacy' && isLegacyProviderId(preset.id)) return newConnection(preset.id, id)
  return {
    id,
    name: displayNameOf(preset).slice(0, 100),
    provider: 'compatible',
    ...(!preset.base_url ? { catalog_provider_id: preset.id } : {}),
    base_url: preset.base_url,
    api_key: '',
    image_api: 'auto',
    image_base_url: '',
  }
}

export function assignAnalysis(
  settings: ModelSettings,
  connection: Connection,
): ModelSettings {
  if (!endpointProviderReady(connection)) return settings
  if (settings.analysis?.connection_id === connection.id) return settings
  // Model source controls model selection, not the chosen provider connection.
  // A following cover moves with analysis; independent ones keep their connection.
  return syncFollowingCover(settings, { ...settings, analysis: cleanBinding(connection.id) })
}

export function ensureCatalogConnection(
  settings: ModelSettings,
  preset: ProviderPreset,
  createLegacy: (provider: ProviderKey) => Connection = newConnection,
  createId: () => string = () => crypto.randomUUID(),
): { settings: ModelSettings; connection?: Connection; changed: boolean } {
  const kind = connectKind(preset)
  if (kind === 'local_asr' || (kind === 'guide' && preset.base_url)) return { settings, changed: false }
  const existing = findCatalogConnection(settings, preset)
  if (existing) {
    if (!settings.analysis && preset.capabilities.includes('language')) {
      return { settings: assignAnalysis(settings, existing), connection: existing, changed: true }
    }
    return { settings, connection: existing, changed: false }
  }
  const connection = kind === 'legacy' && isLegacyProviderId(preset.id)
    ? createLegacy(preset.id)
    : catalogDraftConnection(preset, createId())!
  let next: ModelSettings = { ...settings, connections: [...settings.connections, connection] }
  if (!settings.analysis && preset.capabilities.includes('language') && (kind === 'legacy' || !!preset.base_url)) {
    next = assignAnalysis(next, connection)
  }
  return { settings: next, connection, changed: true }
}

export function catalogPreset(id?: string | null): ProviderPreset | undefined {
  return id ? getProvider(id) : undefined
}

export const CUSTOM_CONNECTION_PREFIX = 'custom:'

export function customConnectionId(selectedId?: string | null): string | undefined {
  return selectedId?.startsWith(CUSTOM_CONNECTION_PREFIX) ? selectedId.slice(CUSTOM_CONNECTION_PREFIX.length) : undefined
}

export function customCatalogId(connectionId: string): string {
  return `${CUSTOM_CONNECTION_PREFIX}${connectionId}`
}

/** A saved OpenAI-compatible row that does not match any catalog preset (custom gateway). */
export function matchedCatalogPreset(connection: Connection): ProviderPreset | undefined {
  const resolved = resolveProviderId(connection.catalog_provider_id || connection.provider) || connection.provider
  const byId = catalogProviders().find(preset => {
    if (preset.id === 'whisper' || preset.id === 'sensevoice') return false
    if (resolved !== preset.id) return false
    return preset.id !== 'openai' || presetKey(connection) === 'openai'
  })
  if (byId) return byId
  if (presetKey(connection) === 'openai') return getProvider('openai')
  const host = catalogHost(connection.base_url)
  if (!host) return undefined
  return catalogProviders().find(preset => (
    catalogHost(preset.base_url) === host && OPENAI_LIKE.has(preset.protocol)
  ))
}

export function isUnmatchedCompatible(connection: Connection): boolean {
  if (connection.provider !== 'compatible' && presetKey(connection) !== 'compatible') return false
  return !matchedCatalogPreset(connection)
}

export function unmatchedCompatibleConnections(settings: ModelSettings): Connection[] {
  return settings.connections.filter(isUnmatchedCompatible)
}
