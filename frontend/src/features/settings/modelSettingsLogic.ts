/**
 * Pure state transitions for the AI model settings document.
 * No React, no i18n: the hook and the tests both call these.
 */
import { endpointProviderReady } from './endpointProvider'
export { endpointProviderReady } from './endpointProvider'
import { PROVIDERS, type ProviderKey } from './providers'
import { getProvider } from './providerPresets'
import type { Assignment, Connection, ModelList, ModelSettings } from './modelSettingsApi'
import { applyModelDefaults, coverFollowsAnalysis, defaultModel, syncFollowingCover } from './modelDefaults'
import { normalizeCompatibleUrl, passed, VISION_HINT_KEY, type ValidationResult } from './providerAccess'
import { collapseSpaces, normalizeProviderBaseUrl } from './providerUrl'
import { isRetryableUpstreamError } from '../../analytics/successRateContract'

export type Role = 'analysis' | 'vision' | 'cover' | 'transcription'
export type SaveIssue = { role: Role; reason: 'provider' | 'model' | 'key' }

const OPENAI_URL = /^https:\/\/api\.openai\.com(?:\/v1)?\/?$/

/** Which picker entry a saved connection belongs to (an OpenAI connection with a foreign address is "compatible"). */
export const presetKey = (c: Connection): ProviderKey =>
  c.provider === 'openai' && c.base_url && !OPENAI_URL.test(c.base_url) ? 'compatible' : c.provider as ProviderKey

/** The connection can actually serve requests: credentials present, or a service that needs none. */
export const connectionReady = (c: Connection) =>
  endpointProviderReady(c) && (!!(c.api_key || c.has_key) || !!PROVIDERS[c.provider as ProviderKey]?.local || (presetKey(c) === 'compatible' && !!c.base_url))

export const cleanBinding = (connection_id: string): Assignment => ({ connection_id, model: '', capability: 'auto', model_source: 'preset' })
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

export const newConnection = (provider: ProviderKey, id: string = crypto.randomUUID()): Connection => {
  const presetUrl = (getProvider(provider)?.base_url || PROVIDERS[provider]?.cloud?.baseUrl || '').trim()
  return {
    id, name: PROVIDERS[provider].name, provider, base_url: presetUrl, api_key: '', image_api: 'auto', image_base_url: '',
    base_url_source: provider === 'compatible' ? 'user' : (presetUrl ? 'preset' : 'user'), preset_version: 0,
  }
}

/** Merge a field edit; changing the address invalidates a stored key so one service's key never reaches another. */
export function editConnection(s: ModelSettings, id: string, patch: Partial<Connection>): ModelSettings {
  const next = { ...patch }
  if (typeof next.api_key === 'string') next.api_key = next.api_key.trim()
  if (typeof next.base_url === 'string') next.base_url = collapseSpaces(next.base_url)
  if (typeof next.image_base_url === 'string') next.image_base_url = collapseSpaces(next.image_base_url)
  const changedAddress = next.base_url !== undefined || next.image_base_url !== undefined
  const changedCreds = changedAddress || next.api_key !== undefined
  return {
    ...s,
    connections: s.connections.map(c => {
      if (c.id !== id) return c
      const merged = {
        ...c,
        ...next,
        ...(changedAddress && c.has_key && next.api_key === undefined ? { api_key: '', has_key: false } : {}),
        ...(typeof next.api_key === 'string' && next.api_key ? { has_key: true } : {}),
        ...(changedCreds ? { validation_status: 'unchecked' as const, validation_error_type: '' } : {}),
      }
      if (next.base_url !== undefined) {
        merged.base_url_source = c.provider === 'compatible' || merged.base_url ? 'user' : 'preset'
      }
      return merged
    }),
  }
}

export function applyValidation(s: ModelSettings, id: string, result: ValidationResult): ModelSettings {
  const ok = passed(result)
  return {
    ...s,
    connections: s.connections.map(c => {
      if (c.id !== id) return c
      const url = result.normalized_base_url && presetKey(c) === 'compatible' ? result.normalized_base_url : c.base_url
      return {
        ...c,
        base_url: url,
        validation_status: ok ? 'ok' : result.result === 'transient' || isRetryableUpstreamError(result.error_type || '') ? 'transient' : 'failed',
        validation_error_type: ok ? '' : (result.error_type || 'unknown'),
      }
    }),
  }
}

/**
 * Point a role at a provider. Saved credentials for that provider are reused; cover/vision
 * bindings keep their connection regardless of whether their model uses smart selection.
 */
export function chooseProvider(
  s: ModelSettings, role: Role, provider: ProviderKey, lists: Record<string, ModelList>, autoCover: boolean,
  create: (provider: ProviderKey) => Connection = newConnection,
): { settings: ModelSettings; connection: Connection; changed: boolean } {
  const oldMainId = s.analysis?.connection_id
  const existing = s.connections.find(c => endpointProviderReady(c) && presetKey(c) === provider && (role === 'analysis' || role === 'transcription' || c.id !== oldMainId))
  const connection = existing || create(provider)
  if (s[role]?.connection_id === connection.id) return { settings: s, connection, changed: false }
  let next: ModelSettings = {
    ...s,
    connections: existing ? s.connections : [...s.connections, connection],
    [role]: role === 'transcription' ? { provider: 'cloud', model: '', connection_id: connection.id, model_source: 'preset' } : cleanBinding(connection.id),
  }
  if (role === 'analysis') next = syncFollowingCover(s, next)
  if (role === 'cover') next = { ...next, cover_follows_analysis: false }
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
  if (!main || !endpointProviderReady(main)) return s
  if (!separate) return { ...s, cover_follows_analysis: true, cover: { ...cleanBinding(main.id), model: defaultModel(main.provider, lists[main.id]?.models || [], true) } }
  const connection = create(presetKey(main))
  return { ...s, cover_follows_analysis: false, connections: [...s.connections, connection], cover: cleanBinding(connection.id) }
}

export function setCoverEnabled(s: ModelSettings, enabled: boolean, lists: Record<string, ModelList>): ModelSettings {
  const main = mainConnection(s)
  if (!enabled) return { ...s, cover_enabled: false }
  if (main && !endpointProviderReady(main)) return s
  return { ...s, cover_enabled: true, ...(!s.cover && main ? { cover_follows_analysis: true, cover: { ...cleanBinding(main.id), model: defaultModel(main.provider, lists[main.id]?.models || [], true) } } : {}) }
}

/** The "画面识别" switch: on = smart selection (multimodal models sample frames), off = subtitles only. */
export function setVisual(s: ModelSettings, enabled: boolean): ModelSettings {
  return { ...s, analysis_mode: enabled ? 'auto' : 'subtitle', allow_visual_screening: enabled }
}

export const isTextOnly = (s: ModelSettings, lists: Record<string, ModelList>) => {
  const binding = s.analysis
  if (!binding?.model) return false
  if (binding.capability !== 'auto') return binding.capability === 'text'
  return lists[binding.connection_id]?.models.find(m => m.id === binding.model)?.capability === 'text'
}

/** The assignment visual understanding follows (explicit vision, else analysis). */
/** Model picked in the cover section: stays following only when it is on the analysis connection. */
export function setCoverModel(s: ModelSettings, connectionId: string, model: string): ModelSettings {
  // E1: an explicit cover model pick is independent; only 「跟随分析」 turns following on.
  return { ...s, cover_enabled: true, cover_follows_analysis: false, cover: { ...cleanBinding(connectionId), model, model_source: 'user' } }
}

export { coverFollowsAnalysis }

export const followedVisionBinding = (s: ModelSettings) => s.vision || s.analysis

export function modelHasVision(binding: Assignment | null | undefined, lists: Record<string, ModelList>): boolean | null {
  if (!binding?.model) return null
  const capability = binding.capability && binding.capability !== 'auto'
    ? binding.capability
    : (lists[binding.connection_id]?.models.find(entry => entry.id === binding.model)?.capability ?? null)
  if (capability === 'multimodal') return true
  if (capability === 'text') return false
  return null
}

/**
 * Same answer as backend `vision_follow_lacks_capability` (D7): only explicit
 * visual mode blocks when the followed model is not confirmed multimodal.
 * Auto + text-only stays open so generation can fall back to subtitles.
 */
export function visionFollowLacksCapability(s: ModelSettings, lists: Record<string, ModelList>): boolean {
  if (s.analysis_mode === 'subtitle') return false
  const binding = followedVisionBinding(s)
  if (!binding?.model) return s.analysis_mode === 'visual'
  const vision = modelHasVision(binding, lists)
  return s.analysis_mode === 'visual' && vision !== true
}

export { VISION_HINT_KEY }

/** First blocking problem before save, in page order. */
export function saveIssue(s: ModelSettings): SaveIssue | null {
  for (const role of ['analysis', 'vision', 'transcription', 'cover'] as const) {
    if (role === 'vision' && !s.vision) continue
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

/** Keep a connection that a role uses, one that already has a key, a keyless local runtime, or a custom URL. */
export function persistableConnection(c: Connection, active: Set<string | undefined>): boolean {
  if (active.has(c.id)) return true
  if (c.api_key || c.has_key) return true
  if (PROVIDERS[c.provider as ProviderKey]?.local) return true
  return presetKey(c) === 'compatible' && !!c.base_url.trim()
}

/** One access check per active connection; shared credentials are checked only once. */
export function validationTargets(s: ModelSettings): { role: Role; connection: Connection; model: string }[] {
  const seen = new Set<string>()
  const targets: { role: Role; connection: Connection; model: string }[] = []
  for (const role of ['analysis', 'vision', 'transcription', 'cover'] as const) {
    if (role === 'transcription' && s.transcription?.provider !== 'cloud') continue
    if (role === 'cover' && !s.cover_enabled) continue
    const binding = s[role]
    const connection = connectionOf(s, role)
    if (!connection || !binding?.model || seen.has(connection.id)) continue
    seen.add(connection.id)
    targets.push({ role, connection, model: binding.model })
  }
  return targets
}

/** Document to send: drop unused blank drafts; keep compatible rows that already have a URL. */
export function forSave(s: ModelSettings): ModelSettings {
  const cover = !s.cover_enabled && !s.cover?.model ? null : s.cover
  const active = new Set([s.analysis?.connection_id, s.vision?.connection_id, cover?.connection_id, s.transcription?.connection_id])
  return {
    ...s,
    cover,
    connections: s.connections
      .filter(c => persistableConnection(c, active))
      .map(c => ({
        ...c,
        api_key: typeof c.api_key === 'string' ? c.api_key.trim() : c.api_key,
        base_url: normalizeProviderBaseUrl(
          presetKey(c) === 'compatible' && c.base_url ? normalizeCompatibleUrl(c.base_url).url : c.base_url,
          c.provider,
        ),
        image_base_url: normalizeProviderBaseUrl(c.image_base_url, 'image'),
      })),
  }
}
