/**
 * Default-model purpose slots (U2).
 *
 * Smart selection is `model_source=preset`: same-provider candidate fallback, never
 * another vendor. Fixed is `model_source=user`. Cover keeps `cover` + `cover_enabled`.
 * `vision === null` follows analysis and warns when that model has no vision.
 * There is no video purpose slot.
 */
import { connectionReady, endpointProviderReady, visionFollowLacksCapability } from './modelSettingsLogic'
export { modelHasVision } from './modelSettingsLogic'
import { enabledModelIds } from './modelVisibility'
import { findCatalogConnection, matchedCatalogPreset } from './providerCatalogView'
import { syncFollowingCover } from './modelDefaults'
import { getCatalog, getProvider, type PurposeId as CatalogPurpose } from './providerPresets'
import type { Assignment, Connection, ModelEntry, ModelList, ModelSettings, ModelSource } from './modelSettingsApi'

export type PurposeId = 'analysis' | 'vision' | 'transcription' | 'cover'
export type SlotKind = 'smart' | 'fixed' | 'local' | 'follow' | 'off' | 'empty'
export type VisionWarning = 'follow' | 'selected'

export const PURPOSE_SLOTS = [
  // kindKey 与目录筛选词对齐（语言 / 语音识别 / 图像生成）；「视觉」仅为标签。
  { id: 'analysis' as const, titleKey: '精彩片段分析', kindKey: '语言' },
  { id: 'vision' as const, titleKey: '画面理解', kindKey: '语言 · 视觉' },
  { id: 'transcription' as const, titleKey: '语音转字幕', kindKey: '语音识别' },
  { id: 'cover' as const, titleKey: '封面生成', kindKey: '图像生成' },
]
export const PURPOSE_IDS = PURPOSE_SLOTS.map(slot => slot.id)
export const COMING_SOON = ['配音 · 语音合成', '配乐 · 音乐'] as const
export const WHISPER_MODELS = ['tiny', 'base', 'small', 'medium', 'large', 'large-v3'] as const
const GROUP_RANK: Record<string, number> = { recommended: 0, popular: 1, local: 2, more: 3 }
const CANDIDATE_KEY: Record<PurposeId, CatalogPurpose> = {
  analysis: 'analysis', vision: 'vision', transcription: 'asr', cover: 'image',
}

export type ModelOffer = {
  modelId: string
  provider: string
  connectionId?: string
  connected: boolean
  displayName: string
}
export type ModelGroup = { modelId: string; offers: ModelOffer[] }
export type SlotLine = { kind: SlotKind; model?: string; provider?: string }

export function resolvedModelSource(binding?: { model?: string; model_source?: ModelSource } | null): ModelSource {
  if (binding?.model_source === 'preset' || binding?.model_source === 'user') return binding.model_source
  return binding?.model ? 'user' : 'preset'
}

export function providerRank(provider: string): number {
  const group = getProvider(provider)?.group
  return group && group in GROUP_RANK ? GROUP_RANK[group] : 4
}

export function assignment(connectionId: string, model: string, source: ModelSource): Assignment {
  return { connection_id: connectionId, model, capability: 'auto', model_source: source }
}

function entryFits(purpose: PurposeId, entry: ModelEntry): boolean {
  if (purpose === 'cover') return !!entry.image
  if (purpose === 'transcription') return !!entry.asr && !!entry.asr_supported && !entry.asr_preview
  if (purpose === 'vision') return !!entry.analysis && entry.capability === 'multimodal'
  return !!entry.analysis
}

function displayName(connection: Connection): string {
  return matchedCatalogPreset(connection)?.short_name || connection.name || connection.provider
}

/** A key is not enough: the access check must have passed. */
function isValidated(connection?: Connection | null): boolean {
  return connection?.validation_status === 'ok'
}

function isAccountList(list?: ModelList): boolean {
  return !!list && !list.preview && (list.source === 'live' || list.source === 'cache')
}

function addOffer(byId: Record<string, ModelOffer[]>, offer: ModelOffer) {
  const list = byId[offer.modelId] || []
  if (list.some(item => item.provider === offer.provider && item.connectionId === offer.connectionId)) return
  list.push(offer)
  byId[offer.modelId] = list
}

/** Models from connected lists, enriched with other catalog providers that offer the same id. */
export function collectModelGroups(settings: ModelSettings, lists: Record<string, ModelList>, purpose: PurposeId): ModelGroup[] {
  const byId: Record<string, ModelOffer[]> = {}
  const key = CANDIDATE_KEY[purpose]
  for (const connection of settings.connections) {
    if (!endpointProviderReady(connection)) continue
    const preset = matchedCatalogPreset(connection)
    const provider = preset?.id || connection.provider
    const list = lists[connection.id]
    const fitting = (list?.models || []).filter(entry => entryFits(purpose, entry))
    // Visibility applies to account lists only. Explicit user choice is strict; the recommendation never empties a purpose.
    const enabled = list && isAccountList(list) ? enabledModelIds(settings, connection, list.models) : null
    const picked = enabled ? fitting.filter(entry => enabled.has(entry.id)) : fitting
    const live = !enabled || Array.isArray(connection.enabled_model_ids) || picked.length ? picked : fitting
    for (const entry of live) {
      addOffer(byId, {
        modelId: entry.id, provider, connectionId: connection.id,
        connected: isValidated(connection) && isAccountList(list), displayName: displayName(connection),
      })
    }
    // A live/cache list with no suitable model is authoritative: do not invent catalog candidates.
  }
  for (const modelId of Object.keys(byId)) {
    const offers = byId[modelId]
    for (const preset of Object.values(getCatalog().providers)) {
      if (!(preset.candidates[key] || []).includes(modelId)) continue
      if (offers.some(item => item.provider === preset.id)) continue
      const candidate = findCatalogConnection(settings, preset)
      if (!preset.base_url && preset.protocol !== 'local' && (!candidate || !endpointProviderReady(candidate))) continue
      const connection = candidate && connectionReady(candidate) ? candidate : undefined
      const list = connection && lists[connection.id]
      if (list && !list.models.some(entry => entry.id === modelId && entryFits(purpose, entry))) continue
      addOffer(byId, {
        modelId, provider: preset.id, connectionId: connection?.id,
        connected: isValidated(connection) && isAccountList(list),
        displayName: preset.short_name || preset.display_name,
      })
    }
  }
  return Object.keys(byId).sort((a, b) => a.localeCompare(b)).map(modelId => ({
    modelId,
    offers: byId[modelId].sort((a, b) => {
      if (a.connected !== b.connected) return a.connected ? -1 : 1
      return providerRank(a.provider) - providerRank(b.provider) || a.provider.localeCompare(b.provider)
    }),
  }))
}

export function preferredOffer(offers: ModelOffer[]): ModelOffer | undefined {
  return [...offers].filter(item => item.connected && item.connectionId)
    .sort((a, b) => providerRank(a.provider) - providerRank(b.provider) || a.provider.localeCompare(b.provider))[0]
}

export function hiddenNonVisionCount(lists: Record<string, ModelList>): number {
  const ids = new Set<string>()
  for (const list of Object.values(lists)) {
    for (const entry of list.models) {
      if (entry.analysis && entry.capability !== 'multimodal') ids.add(entry.id)
    }
  }
  return ids.size
}

/** Use the same capability decision as readiness; saving remains allowed. */
export function visionWarning(settings: ModelSettings, lists: Record<string, ModelList>): VisionWarning | null {
  if (!visionFollowLacksCapability(settings, lists)) return null
  return settings.vision ? 'selected' : 'follow'
}

function connectionName(settings: ModelSettings, id?: string): string | undefined {
  const connection = settings.connections.find(item => item.id === id)
  return connection ? displayName(connection) : undefined
}

export function slotSummary(settings: ModelSettings, _lists: Record<string, ModelList>, purpose: PurposeId): SlotLine {
  if (purpose === 'cover' && !settings.cover_enabled) return { kind: 'off' }
  if (purpose === 'vision' && !settings.vision) {
    return settings.analysis?.model ? { kind: 'follow', model: settings.analysis.model } : { kind: 'empty' }
  }
  if (purpose === 'transcription') {
    const value = settings.transcription
    if (!value?.model) return { kind: 'empty' }
    if (value.provider !== 'cloud') return { kind: 'local', model: value.model, provider: value.provider }
    return {
      kind: resolvedModelSource(value) === 'preset' ? 'smart' : 'fixed',
      model: value.model, provider: connectionName(settings, value.connection_id),
    }
  }
  const binding = settings[purpose]
  if (!binding?.model) return { kind: 'empty' }
  return {
    kind: resolvedModelSource(binding) === 'preset' ? 'smart' : 'fixed',
    model: binding.model, provider: connectionName(settings, binding.connection_id),
  }
}

function bindPurpose(settings: ModelSettings, purpose: PurposeId, connectionId: string, model: string, source: ModelSource): ModelSettings {
  const connection = settings.connections.find(row => row.id === connectionId)
  if (!connection || !endpointProviderReady(connection)) return settings
  if (purpose === 'transcription') {
    return { ...settings, transcription: { provider: 'cloud', connection_id: connectionId, model, model_source: source } }
  }
  if (purpose === 'cover') {
    // E1: picking a fixed or smart cover model is an explicit provider choice → independent.
    // Only the 「跟随分析」 entry (setCoverSeparate(false)) turns following on.
    return { ...settings, cover_enabled: true, cover_follows_analysis: false, cover: assignment(connectionId, model, source) }
  }
  const next = { ...settings, [purpose]: assignment(connectionId, model, source) }
  return purpose === 'analysis' ? syncFollowingCover(settings, next) : next
}

export function applySmartSelection(settings: ModelSettings, purpose: PurposeId, model: string, connectionId: string): ModelSettings {
  return bindPurpose(settings, purpose, connectionId, model, 'preset')
}

export function applyFixedSelection(settings: ModelSettings, purpose: PurposeId, model: string, connectionId: string): ModelSettings {
  return bindPurpose(settings, purpose, connectionId, model, 'user')
}

export function applyVisionFollow(settings: ModelSettings): ModelSettings {
  return { ...settings, vision: null }
}

/** Cover off keeps the existing `cover` assignment; only `cover_enabled` flips. */
export function applyCoverOff(settings: ModelSettings): ModelSettings {
  return { ...settings, cover_enabled: false }
}

/** 「改用云端转写」tries configured accounts in this order.
 * 88API and Infistar have no usable speech model, so they are not offered. */
const CLOUD_TRANSCRIPTION_ORDER = ['dashscope', 'openai'] as const

/** A list that never arrives should still open Bailian setup. */
export const CLOUD_TRANSCRIPTION_WAIT_MS = 10_000

export type CloudTranscriptionChoice =
  | { kind: 'selected'; settings: ModelSettings; provider: string; providerLabel: string; model: string }
  | { kind: 'add'; provider: 'dashscope' }
  | { kind: 'wait' }
  | { kind: 'idle' }

function connectionReadyForCloud(connection: Connection | undefined): connection is Connection {
  return !!connection && endpointProviderReady(connection) && !!(connection.api_key?.trim() || connection.has_key)
}

/** Account list is still in flight only when this connection has no entry yet.
 * A preview or catalog payload is a finished, unusable answer (failed discover). */
function cloudListStatus(list: ModelList | undefined): 'loading' | 'unusable' | 'ready' {
  if (!list) return 'loading'
  if (list.preview || list.source === 'catalog' || (list.source !== 'live' && list.source !== 'cache')) return 'unusable'
  return 'ready'
}

function usableCloudAsr(list: ModelList, modelId: string): boolean {
  const entry = list.models.find(model => model.id === modelId)
  return !!entry?.asr && !!entry.asr_supported && !entry.asr_preview
}

function selectedCloud(
  settings: ModelSettings, providerId: string, label: string, model: string, connectionId: string,
): Extract<CloudTranscriptionChoice, { kind: 'selected' }> {
  return {
    kind: 'selected', provider: providerId, providerLabel: label, model,
    settings: applySmartSelection(settings, 'transcription', model, connectionId),
  }
}

/** Ready accounts in provider order. The cloud flow discovers each of these, not only the open row. */
export function cloudTranscriptionDiscoverTargets(settings: ModelSettings): Connection[] {
  const targets: Connection[] = []
  for (const providerId of CLOUD_TRANSCRIPTION_ORDER) {
    const preset = getProvider(providerId)
    const connection = preset ? findCatalogConnection(settings, preset) : undefined
    if (connectionReadyForCloud(connection)) targets.push(connection)
  }
  return targets
}

/** Pick a cloud transcription the account can already run.
 * Bailian may use its preset before any list arrives. Every other provider waits
 * only while its list is absent. A preview or catalog result is unusable and the
 * next account is tried. `timedOut` stops waiting and opens Bailian when none fit. */
export function applyCloudTranscription(
  settings: ModelSettings,
  lists: Record<string, ModelList> = {},
  options: { timedOut?: boolean } = {},
): Exclude<CloudTranscriptionChoice, { kind: 'idle' }> {
  let unresolved = false
  for (const providerId of CLOUD_TRANSCRIPTION_ORDER) {
    const preset = getProvider(providerId)
    const connection = preset ? findCatalogConnection(settings, preset) : undefined
    if (!preset || !connectionReadyForCloud(connection)) continue
    const preferred = preset.candidates.asr || []
    const list = lists[connection.id]
    const status = cloudListStatus(list)
    if (status === 'loading') {
      if (providerId === 'dashscope' && preferred[0]) {
        return selectedCloud(settings, providerId, preset.short_name || preset.display_name, preferred[0], connection.id)
      }
      if (!options.timedOut) {
        unresolved = true
        break
      }
      continue
    }
    if (status !== 'ready' || !list) continue
    const model = preferred.find(id => usableCloudAsr(list, id)) || ''
    if (!model) continue
    return selectedCloud(settings, providerId, preset.short_name || preset.display_name, model, connection.id)
  }
  return unresolved ? { kind: 'wait' } : { kind: 'add', provider: 'dashscope' }
}

export function cloudTranscriptionWaitExpired(startedAt: number, now: number): boolean {
  return now - startedAt >= CLOUD_TRANSCRIPTION_WAIT_MS
}

/** The settings page only switches when the user opened 「改用云端转写」. */
export function applyRequestedCloudTranscription(
  requestedProvider: string,
  settings: ModelSettings,
  lists: Record<string, ModelList> = {},
  options: { timedOut?: boolean } = {},
): CloudTranscriptionChoice {
  if (requestedProvider !== 'cloud') return { kind: 'idle' }
  return applyCloudTranscription(settings, lists, options)
}

/** Save patch after 「改用云端转写」 opened Bailian setup.
 * Empty until a configured account can transcribe, so a save outside this flow keeps local Whisper. */
export function cloudTranscriptionSavePatch(
  pending: boolean,
  settings: ModelSettings,
  lists: Record<string, ModelList> = {},
): Partial<ModelSettings> | undefined {
  if (!pending) return undefined
  const chosen = applyCloudTranscription(settings, lists)
  return chosen.kind === 'selected' ? { transcription: chosen.settings.transcription } : undefined
}

export function applyLocalTranscription(
  settings: ModelSettings, provider: 'whisper_local' | 'sensevoice_local', model: string,
): ModelSettings {
  return { ...settings, transcription: { provider, model, model_source: 'user' } }
}

/** Enums and booleans only — never model ids, keys, URLs, or user content. */
export function slotTelemetry(settings: ModelSettings, lists: Record<string, ModelList>) {
  return {
    analysis_source: settings.analysis?.model ? resolvedModelSource(settings.analysis) : 'none',
    vision_source: settings.vision ? resolvedModelSource(settings.vision) : 'follow',
    cover_source: settings.cover_enabled ? (settings.cover?.model ? resolvedModelSource(settings.cover) : 'none') : 'frame',
    transcription_source: !settings.transcription ? 'none'
      : settings.transcription.provider !== 'cloud' ? settings.transcription.provider
      : resolvedModelSource(settings.transcription),
    vision_follow_lacks_vision: visionWarning(settings, lists) !== null,
  }
}

export function isSmartSelected(settings: ModelSettings, purpose: PurposeId, modelId: string, offer: ModelOffer): boolean {
  const preferred = preferredOffer([offer])
  if (!preferred?.connectionId || preferred.modelId !== modelId) return false
  if (purpose === 'cover' && !settings.cover_enabled) return false
  if (purpose === 'vision' && !settings.vision) return false
  if (purpose === 'transcription') {
    const value = settings.transcription
    return value?.provider === 'cloud' && value.model === modelId && value.connection_id === preferred.connectionId && resolvedModelSource(value) === 'preset'
  }
  const binding = settings[purpose]
  return binding?.model === modelId && binding.connection_id === preferred.connectionId && resolvedModelSource(binding) === 'preset'
}

export function isFixedSelected(settings: ModelSettings, purpose: PurposeId, modelId: string, offer: ModelOffer): boolean {
  if (!offer.connectionId) return false
  if (purpose === 'cover' && !settings.cover_enabled) return false
  if (purpose === 'vision' && !settings.vision) return false
  if (purpose === 'transcription') {
    const value = settings.transcription
    return value?.provider === 'cloud' && value.model === modelId && value.connection_id === offer.connectionId && resolvedModelSource(value) === 'user'
  }
  const binding = settings[purpose]
  return binding?.model === modelId && binding.connection_id === offer.connectionId && resolvedModelSource(binding) === 'user'
}
