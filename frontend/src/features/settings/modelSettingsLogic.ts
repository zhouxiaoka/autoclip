/**
 * Pure state transitions for the AI model settings document.
 * No React, no i18n: the hook and the tests both call these.
 */
import { PROVIDERS, type ProviderKey } from './providers'
import type { Assignment, Connection, ModelList, ModelSettings } from './modelSettingsApi'
import { applyModelDefaults, defaultModel } from './modelDefaults'

export type Role = 'analysis' | 'vision' | 'cover' | 'transcription'
export type SaveIssue = { role: 'analysis' | 'cover' | 'transcription'; reason: 'provider' | 'model' | 'key' }

const OPENAI_URL = /^https:\/\/api\.openai\.com(?:\/v1)?\/?$/

/** Which picker entry a saved connection belongs to (an OpenAI connection with a foreign address is "compatible"). */
export const presetKey = (c: Connection): ProviderKey =>
  c.provider === 'openai' && c.base_url && !OPENAI_URL.test(c.base_url) ? 'compatible' : c.provider as ProviderKey

/** Enough information to list models: a key, a custom address, or a keyless local preset. */
export const canDiscover = (c: Connection) => !!(c.api_key || c.has_key || c.base_url || PROVIDERS[c.provider as ProviderKey]?.local)

/** The connection can actually serve requests: credentials present, or a service that needs none. */
export const connectionReady = (c: Connection) =>
  !!(c.api_key || c.has_key) || !!PROVIDERS[c.provider as ProviderKey]?.local || (presetKey(c) === 'compatible' && !!c.base_url)

export const cleanBinding = (connection_id: string): Assignment => ({ connection_id, model: '', capability: 'auto' })
export const mainConnection = (s: ModelSettings) => s.connections.find(c => c.id === s.analysis?.connection_id)
export const connectionOf = (s: ModelSettings, role: Role) => s.connections.find(c => c.id === s[role]?.connection_id)

/** First run: nothing saved yet and the main connection cannot serve requests. */
export const needsSetup = (s: ModelSettings) => {
  const main = mainConnection(s)
  return !s.saved && (!main || !connectionReady(main))
}

/**
 * Loaded document → editable state. On first run nothing is pre-selected: the user picks a provider and
 * the recommendation follows the key. Covers are designed locally (free) until the user picks an image
 * model themselves: no account with any image service is assumed.
 */
export function prepareLoaded(value: ModelSettings): ModelSettings {
  if (value.migration_warnings?.length) return value
  if (!needsSetup(value)) return value
  return { ...value, analysis: null, cover: null, vision: null, cover_enabled: false, allow_send_frame: true }
}

/** AI covers are opt-in; once chosen, a service without any image model falls back to the designed cover instead of blocking save. */
export function coverFallback(s: ModelSettings, lists: Record<string, ModelList>): ModelSettings {
  if (!s.cover_enabled || s.cover?.model) return s
  const connection = connectionOf(s, 'cover') || mainConnection(s)
  const list = connection && lists[connection.id]
  if (list && !list.models.some(m => m.image)) return { ...s, cover_enabled: false, cover: null }
  return s
}

export const newConnection = (provider: ProviderKey, id: string = crypto.randomUUID()): Connection =>
  ({ id, name: PROVIDERS[provider].name, provider, base_url: '', api_key: '', image_api: 'auto', image_base_url: '' })

/** Merge a field edit; changing the address invalidates a stored key so one service's key never reaches another. */
export function editConnection(s: ModelSettings, id: string, patch: Partial<Connection>): ModelSettings {
  const changedAddress = patch.base_url !== undefined || patch.image_base_url !== undefined
  return { ...s, connections: s.connections.map(c => c.id === id ? { ...c, ...patch, ...(changedAddress && c.has_key ? { api_key: '', has_key: false } : {}) } : c) }
}

/**
 * Point a role at a provider. Saved credentials for that provider are reused, but the analysis
 * connection is never shared with cover/vision so a provider switch cannot move a key across roles.
 */
export function chooseProvider(
  s: ModelSettings, role: Role, provider: ProviderKey, lists: Record<string, ModelList>, autoCover: boolean,
  create: (provider: ProviderKey) => Connection = newConnection,
): { settings: ModelSettings; connection: Connection; changed: boolean } {
  const oldMainId = s.analysis?.connection_id
  const existing = s.connections.find(c => presetKey(c) === provider && (role === 'analysis' || role === 'transcription' || c.id !== oldMainId))
  const connection = existing || create(provider)
  if (s[role]?.connection_id === connection.id) return { settings: s, connection, changed: false }
  let next: ModelSettings = {
    ...s,
    connections: existing ? s.connections : [...s.connections, connection],
    [role]: role === 'transcription' ? { provider: 'cloud', model: '', connection_id: connection.id } : cleanBinding(connection.id),
  }
  if (role === 'analysis') {
    if (s.cover?.connection_id === oldMainId) next.cover = s.cover_enabled ? cleanBinding(connection.id) : null
    if (s.vision?.connection_id === oldMainId) next.vision = null
  }
  const cached = lists[connection.id]
  if (cached && !cached.preview) next = applyModelDefaults(next, connection, cached.models, autoCover)
  return { settings: next, connection, changed: true }
}

/** Cover either follows the analysis connection or gets its own (same provider, separate key). */
export function setCoverSeparate(
  s: ModelSettings, separate: boolean, lists: Record<string, ModelList>,
  create: (provider: ProviderKey) => Connection = newConnection,
): ModelSettings {
  const main = mainConnection(s)
  if (!main) return s
  if (!separate) return { ...s, cover: { ...cleanBinding(main.id), model: defaultModel(main.provider, lists[main.id]?.models || [], true) } }
  const connection = create(presetKey(main))
  return { ...s, connections: [...s.connections, connection], cover: cleanBinding(connection.id) }
}

export function setCoverEnabled(s: ModelSettings, enabled: boolean, lists: Record<string, ModelList>): ModelSettings {
  const main = mainConnection(s)
  if (!enabled) return { ...s, cover_enabled: false }
  return { ...s, cover_enabled: true, ...(!s.cover && main ? { cover: { ...cleanBinding(main.id), model: defaultModel(main.provider, lists[main.id]?.models || [], true) } } : {}) }
}

/** The "画面识别" switch: on = smart selection (multimodal models sample frames), off = subtitles only. */
export function setVisual(s: ModelSettings, enabled: boolean): ModelSettings {
  return { ...s, analysis_mode: enabled ? 'auto' : 'subtitle', allow_visual_screening: enabled, vision: null }
}

export const isTextOnly = (s: ModelSettings, lists: Record<string, ModelList>) => {
  const binding = s.analysis
  if (!binding?.model) return false
  if (binding.capability !== 'auto') return binding.capability === 'text'
  return lists[binding.connection_id]?.models.find(m => m.id === binding.model)?.capability === 'text'
}

/** First blocking problem before save, in page order. */
export function saveIssue(s: ModelSettings): SaveIssue | null {
  for (const role of ['analysis', 'transcription', 'cover'] as const) {
    if (role === 'transcription' && s.transcription?.provider !== 'cloud') continue
    if (role === 'cover' && !s.cover_enabled) continue
    const binding = s[role]
    const connection = s.connections.find(c => c.id === binding?.connection_id)
    if (!connection) return { role, reason: 'provider' }
    if (!binding?.model) return { role, reason: 'model' }
    if (connection && !connectionReady(connection)) return { role, reason: 'key' }
  }
  return null
}

/** Document to send: drop blank compatible connections nothing points at; a disabled cover with no model is null. */
export function forSave(s: ModelSettings): ModelSettings {
  const cover = !s.cover_enabled && !s.cover?.model ? null : s.cover
  const active = new Set([s.analysis?.connection_id, s.vision?.connection_id, cover?.connection_id, s.transcription?.connection_id])
  return { ...s, cover, connections: s.connections.filter(c => c.provider !== 'compatible' || c.base_url.trim() || active.has(c.id)) }
}
