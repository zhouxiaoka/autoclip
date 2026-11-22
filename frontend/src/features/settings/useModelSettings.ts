import { useEffect, useRef, useState } from 'react'
import { codeFromRequestError, codeFromResult, safeHttpStatus } from '../../analytics/connectionTestCode'
import { message } from 'antd'
import { t } from '../../i18n'
import { errorText } from '../studio/api'
import { beginDebouncedEditDiscovery, beginExperience, claimModelSettingsLoad, connectionSignature, shouldReportModelDiscovery, trackProviderValidation, type Placement } from '../../analytics/experience'
import { hintKeyForUpstreamError, isRetryableUpstreamError, telemetryProvider } from '../../analytics/successRateContract'
import { type ProviderKey } from './providers'
import { bindingCapability, modelSettingsApi, type Connection, type FetchListResult, type ModelList, type ModelSettings } from './modelSettingsApi'
import { quickConnectPatch } from './quickConnect'
import { pickRecommendedTestModel, preserveFixedAssignments, recommendProviderSetup } from './providerModelSetup'
import { applyModelDefaults, syncFollowingCover } from './modelDefaults'
import { enabledModelIds } from './modelVisibility'
import { slotTelemetry } from './defaultModelSlots'
import * as logic from './modelSettingsLogic'
import { assignAnalysis, catalogDraftConnection, catalogPreset, ensureCatalogConnection, selectLocalAsr, type LocalAsrId } from './providerCatalogView'
import { getProvider } from './providerPresets'
import type { Role, SaveIssue } from './modelSettingsLogic'
import { passed, telemetryHost, validationCopy, IMAGE_MODEL_IN_ANALYSIS, VISION_HINT_KEY, type ValidationResult } from './providerAccess'
import { analysisImageMisconfigCopy } from './defaultModelSlots'

import { applyCustomProvider, emptyDraft, emptyOffer, mergeCustomList, type CustomProviderDraft } from './customProvider'
import { isImageMarker } from './modelKind'
import { notifySettingsSaved } from '../studio/settingsReturn'
import { CUSTOM_PROVIDER_ID, planPlacement, saveToast, type GuideEndpoint } from './keyGuide'
import { registerKeyGuideApplier, stagePendingSelect, takePendingRequest, type KeyGuideRequest } from './keyGuideBus'


/** 1.5.7: every failed connection test carries a closed-set code (+ integer HTTP status). */
function connectionTestFailure(value: ValidationResult): Record<string, unknown> {
  const status = safeHttpStatus(value.http_status)
  return { error_code: codeFromResult(value), ...(status ? { http_status: status } : {}) }
}

export const roleLabel = (role: Role) =>
  ({ analysis: t('模型'), vision: t('画面理解模型'), cover: t('生图模型'), transcription: t('转写模型') })[role]

export const issueText = (issue: SaveIssue) =>
  issue.reason === 'provider' ? t('请先选择一家 AI 服务')
    : issue.reason === 'image_model' ? t('该模型是生图模型，只能用于封面，不能做分析。')
    : `${roleLabel(issue.role)}：${issue.reason === 'model' ? t('请先选择模型') : t('请填写 API Key')}`

export type ModelSettingsStore = ReturnType<typeof useModelSettings>

/** Prefer analysisImageMisconfigCopy when the probe returned the image-slot miss + recommend. */
function failureCopy(result: ValidationResult, model?: string) {
  const imageMiss = result.error_code === IMAGE_MODEL_IN_ANALYSIS
    || result.error_type === IMAGE_MODEL_IN_ANALYSIS
  if (imageMiss && model) {
    const recommend = result.recommended?.analysis?.[0] || ''
    return analysisImageMisconfigCopy(model, recommend)
  }
  return validationCopy(result.error_type, result.hint_key)
}


function probeVision(settings: ModelSettings, role: Role, lists: Record<string, ModelList>) {
  return role === 'vision' || (role === 'analysis' && (settings.analysis_mode === 'visual'
    || (settings.analysis_mode === 'auto' && bindingCapability(settings.analysis, lists) === 'multimodal')))
}

/** Compare validation inputs only in memory. Never send this signature to analytics or persistence. */
function probeSignature(connection: Connection, model: string, vision: boolean, role: Role) {
  return JSON.stringify([connection.id, connection.provider, connection.catalog_provider_id, connection.base_url,
    connection.image_base_url, connection.image_api, connection.api_key, !!connection.has_key, model, vision, role])
}

/**
 * One editable copy of the AI model document, shared by the settings page and the first-run card.
 * Editing a key or address triggers one debounced discovery; recommendations fill empty slots only.
 */
export function useModelSettings(placement: Placement = 'settings_model', requireCloudTranscription = false) {
  const [settings, setSettings] = useState<ModelSettings | null>(null)
  const [lists, setLists] = useState<Record<string, ModelList>>({})
  const [busy, setBusy] = useState<Record<string, boolean>>({})
  const [listErrors, setListErrors] = useState<Record<string, string>>({})
  const [dirty, setDirtyState] = useState(false)
  // A save can navigate before React commits its next render.
  const dirtyRef = useRef(false)
  const setDirty = (value: boolean) => { dirtyRef.current = value; setDirtyState(value) }
  const [conflicted, setConflicted] = useState(false)
  const [saving, setSaving] = useState(false)
  const [matching, setMatching] = useState(false)
  const matchingRef = useRef(false)
  const [testing, setTesting] = useState(false)
  const [testingKind, setTestingKind] = useState<'quick' | 'trial' | null>(null)
  const [lastTrialByConnection, setLastTrialByConnection] = useState<Record<string, ValidationResult>>({})
  const trialAbortRef = useRef<AbortController | null>(null)
  const [error, setError] = useState('')
  const [testWarning, setTestWarning] = useState<{ id: string; text: string } | null>(null)
  const [keyHints, setKeyHints] = useState<Record<string, string>>({})
  const versions = useRef<Record<string, number>>({})
  const alive = useRef(true)
  // First-run discovery may suggest a cover. Reopening a saved document preserves an unassigned slot.
  const autoCover = useRef(false)
  const settingsRef = useRef(settings)
  const listsRef = useRef(lists)
  listsRef.current = lists
  settingsRef.current = settings
  const tested = useRef(new Map<string, string>())
  const savedRef = useRef<ModelSettings | null>(null)
  // Signature of the last loaded or saved document. The post-load rediscovery is not an edit.
  const loadedSignature = useRef<string | null>(null)
  const summary = (value: ModelSettings) => ({
    placement, provider: telemetryProvider(logic.mainConnection(value)?.provider),
    changed_connections: JSON.stringify(savedRef.current?.connections) !== JSON.stringify(value.connections), mode: value.saved ? 'update' : 'initial', analysis_mode: value.analysis_mode,
    analysis_configured: !!value.analysis?.model, vision_configured: !!value.vision?.model,
    cover_configured: !!value.cover?.model, transcription_configured: !!value.transcription?.model,
    transcription_mode: value.transcription?.provider || 'unknown', cover_mode: value.cover_enabled && value.cover?.model ? 'ai' : 'frame',
    cover_separate: !!value.cover && value.cover.connection_id !== value.analysis?.connection_id,
    ...slotTelemetry(value, lists),
    ...Object.fromEntries(['analysis', 'vision', 'cover', 'transcription'].map(role => [
      `changed_${role}`, JSON.stringify(savedRef.current?.[role as Role]) !== JSON.stringify(value[role as Role]),
    ])),
  })

  const update = (patch: Partial<ModelSettings>) => {
    setSettings(old => old ? { ...old, ...patch } : old)
    if (!conflicted) setError('')
    setDirty(true)
  }
  const replace = (next: ModelSettings) => { setSettings(next); setDirty(true); setError('') }

  const discoveryProperties = (connection: Connection, trigger: 'load' | 'edit' | 'provider_change' | 'manual') =>
    ({ placement, provider: telemetryProvider(connection.provider), trigger })

  const discover = async (connection: Connection, refresh = false, trigger: 'load' | 'edit' | 'provider_change' | 'manual' = 'manual') => {
    if (connection.provider === 'compatible' && !connection.base_url) return
    const reported = discoveryProperties(connection, trigger)
    const finish: (outcome: 'completed' | 'failed' | 'blocked', extra?: Record<string, unknown>, error?: unknown) => void =
      shouldReportModelDiscovery(trigger, connectionSignature(settingsRef.current), loadedSignature.current)
        ? (trigger === 'edit' ? beginDebouncedEditDiscovery(reported) : beginExperience('model_discovery', reported))
        : () => {}
    const version = (versions.current[connection.id] || 0) + 1
    versions.current[connection.id] = version
    setBusy(old => ({ ...old, [connection.id]: true }))
    try {
      const result = await modelSettingsApi.discover(connection, refresh)
      if (!alive.current || versions.current[connection.id] !== version) return
      const merged = mergeCustomList(connection, result)
      const before = settingsRef.current
      const after = before && !merged.preview ? applyModelDefaults(before, connection, merged.models, autoCover.current) : before
      finish('completed', { source: merged.source, preview: !!merged.preview, has_warning: !!merged.warning, result_count: merged.models.length, defaults_applied: JSON.stringify(before) !== JSON.stringify(after) })
      setLists(old => ({ ...old, [connection.id]: merged }))
      setListErrors(old => { const next = { ...old }; delete next[connection.id]; return next })
      setSettings(old => old && !merged.preview ? applyModelDefaults(old, connection, merged.models, autoCover.current) : old)
    } catch (e) {
      if (alive.current && versions.current[connection.id] === version) { finish('failed', {}, e); setListErrors(old => ({ ...old, [connection.id]: errorText(e) })) }
    } finally {
      if (alive.current && versions.current[connection.id] === version) setBusy(old => ({ ...old, [connection.id]: false }))
    }
  }

  const load = async () => {
    setError('')
    try {
      const value = logic.prepareLoaded(await modelSettingsApi.get())
      if (!alive.current) return
      // Remounts and repeat reads of the same document are not another load.
      if (claimModelSettingsLoad(placement, value)) beginExperience('model_settings_load', { placement })('completed')
      loadedSignature.current = connectionSignature(value)
      tested.current.clear()
      savedRef.current = value
      setDirty(false); setConflicted(false)
      autoCover.current = !value.saved && !value.prefer_local_cover && !value.cover
      setSettings(value)
      setLists(old => {
        const next = { ...old }
        value.connections.forEach(connection => {
          if (connection.custom_models?.length) next[connection.id] = mergeCustomList(connection, next[connection.id])
        })
        return next
      })
      value.connections.forEach(c => { void discover(c, false, 'load') })
    } catch (e) { if (alive.current) { beginExperience('model_settings_load', { placement })('failed', {}, e); setError(errorText(e)) } }
  }
  useEffect(() => { alive.current = true; void load(); return () => { alive.current = false } }, [])

  const signature = connectionSignature(settings)
  // Product discovery stays on this timer. Edit analytics wait out the burst separately,
  // and a rediscovery of the loaded document does not count as an edit.
  useEffect(() => {
    if (!settings) return
    const timer = window.setTimeout(() => settingsRef.current?.connections.forEach(c => { void discover(c, false, 'edit') }), 650)
    return () => window.clearTimeout(timer)
  }, [signature])

  useEffect(() => {
    if (!dirty) return
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  const editConnection = (connection: Connection, patch: Partial<Connection>) => {
    if (!settings) return
    versions.current[connection.id] = (versions.current[connection.id] || 0) + 1
    setTestWarning(current => (current?.id === connection.id ? null : current))
    update(logic.editConnection(settings, connection.id, patch))
    setLists(old => { const next = { ...old }; delete next[connection.id]; return next })
  }
  const declareModel = (connection: Connection, id: string, role: 'analysis' | 'vision' | 'cover' | '') => {
    if (!settings) return
    const current = lists[connection.id]
    const entry = current?.models.find(row => row.id === id)
    if (!entry?.manual_roles || (role && !entry.manual_roles.includes(role))) return
    const offers = (connection.custom_models || []).filter(offer => offer.id !== id)
    if (role) offers.push({
      ...emptyOffer(id), types: role === 'cover' ? ['image'] : ['language'], vision: role === 'vision',
      scenarios: role === 'vision' ? ['analysis', 'vision'] : [role],
    })
    const enabled = new Set(enabledModelIds(settings, connection, current.models))
    if (role) enabled.add(id)
    const next = { ...connection, custom_models: offers, enabled_model_ids: [...enabled] }
    const models = current.models.map(row => row.id !== id ? row : {
      ...row, kind: 'other' as const, capability: null, capability_source: undefined, analysis: false, image: false,
    })
    versions.current[connection.id] = (versions.current[connection.id] || 0) + 1
    setBusy(old => ({ ...old, [connection.id]: false }))
    setLists(old => ({ ...old, [connection.id]: mergeCustomList(next, { ...current, models }) }))
    update({ connections: settings.connections.map(c => c.id === next.id ? next : c) })
  }
  const chooseProvider = (role: Role, provider: ProviderKey) => {
    if (!settings) return
    const result = logic.chooseProvider(settings, role, provider, lists, autoCover.current)
    if (!result.changed) return
    replace(result.settings)
    void discover(result.connection, false, 'provider_change')
  }
  const ensureCatalogProvider = (id: string, patch?: Partial<Connection>, useForAnalysis = false) => {
    if (!settings) return
    const preset = getProvider(id)
    if (!preset) return
    const result = ensureCatalogConnection(settings, preset)
    let next = result.settings
    let connection = result.connection
    if (connection && patch) {
      next = logic.editConnection(next, connection.id, patch)
      connection = next.connections.find(row => row.id === connection!.id)
    }
    if (connection && useForAnalysis) next = assignAnalysis(next, connection)
    if (result.changed || patch || useForAnalysis) {
      if (connection) {
        const cached = lists[connection.id]
        if (cached && !cached.preview) next = applyModelDefaults(next, connection, cached.models, autoCover.current)
      }
      replace(next)
    }
    if (connection) void discover(connection, false, 'provider_change')
    return connection?.id
  }
  const assignAnalysisConnection = (connection: Connection) => {
    if (!settings) return
    let next = assignAnalysis(settings, connection)
    const cached = lists[connection.id]
    if (cached && !cached.preview) next = applyModelDefaults(next, connection, cached.models, autoCover.current)
    replace(next)
  }
  const selectLocalAsrProvider = (id: LocalAsrId) => {
    if (!settings) return
    replace(selectLocalAsr(settings, id))
  }
  const setTranscriptionLocal = (model: string) => update({ transcription: { provider: 'whisper_local', model, model_source: 'user' } })
  const setCoverSeparate = (separate: boolean) => { if (settings) replace(logic.setCoverSeparate(settings, separate, lists)) }
  const setCoverEnabled = (enabled: boolean) => { autoCover.current = false; if (settings) replace(logic.setCoverEnabled(settings, enabled, lists)) }
  const setCoverModel = (connectionId: string, model: string) => { if (!settings) return; autoCover.current = false; replace(logic.setCoverModel(settings, connectionId, model)) }
  const setVisual = (enabled: boolean) => { if (settings) replace(logic.setVisual(settings, enabled)) }
  const clearConnectionKey = async (id: string) => {
    if (!settings) return
    const cleared = logic.clearConnectionKey(settings, id)
    const next = logic.saveIssue(cleared, true)
      ? {
          ...cleared,
          analysis: cleared.analysis?.connection_id === id ? null : cleared.analysis,
          vision: cleared.vision?.connection_id === id ? null : cleared.vision,
          cover: cleared.cover?.connection_id === id ? null : cleared.cover,
          cover_enabled: cleared.cover?.connection_id === id ? false : cleared.cover_enabled,
          cover_follows_analysis: cleared.cover?.connection_id === id ? false : cleared.cover_follows_analysis,
        }
      : cleared
    replace(next)
    await save(undefined, next, undefined, false)
  }
  const removeConnection = async (id: string) => {
    if (!settings) return
    const next = logic.removeConnection(settings, id)
    replace(next)
    await save(undefined, next, undefined, false)
  }
  const addCustomProvider = (draft: CustomProviderDraft) => {
    if (!settings) return
    const next = applyCustomProvider(settings, draft)
    const connection = next.connections[next.connections.length - 1]
    replace(next)
    if (connection) setLists(old => ({ ...old, [connection.id]: mergeCustomList(connection) }))
  }

  const emitValidation = (connection: Connection, result: ValidationResult) => {
    const provider = telemetryProvider(connection.provider)
    trackProviderValidation({
      provider,
      base_url_host: result.base_url_host || telemetryHost(connection.base_url),
      result: passed(result) ? 'success' : 'failed',
      probe_kind: result.probe_kind || 'quick',
      ...(typeof result.trial_context_ok === 'boolean' ? { trial_context_ok: result.trial_context_ok } : {}),
      ...(typeof result.trial_rate_limited === 'boolean' ? { trial_rate_limited: result.trial_rate_limited } : {}),
      ...(typeof result.trial_json_ok === 'boolean' ? { trial_json_ok: result.trial_json_ok } : {}),
      ...(typeof result.trial_avg_ms === 'number' ? { trial_avg_ms: result.trial_avg_ms } : {}),
      ...(passed(result) ? {} : { upstream_error_type: result.error_type || 'unknown' }),
    })
    if (result.key_hint) setKeyHints(old => ({ ...old, [connection.id]: result.key_hint as string }))
    if (result.probe_kind === 'trial') {
      setLastTrialByConnection(old => ({ ...old, [connection.id]: result }))
    }
  }

  /** Keep a non-blocking list warning on screen. Returns the copy when the test itself passed. */
  const acceptWarning = (connectionId: string, result: ValidationResult) => {
    if (passed(result) && result.warning) {
      const text = t(result.warning)
      setTestWarning({ id: connectionId, text })
      return text
    }
    setTestWarning(current => (current?.id === connectionId ? null : current))
    return ''
  }

  const orderedIds = (listing?: { models?: string[]; recommended?: Record<string, string[]> }) => {
    const analysis = listing?.recommended?.analysis || []
    const live = listing?.models || []
    return analysis.length ? [...analysis, ...live.filter(id => !analysis.includes(id))] : live
  }

  // ID-only responses do not establish what a model supports. Retain evidence from discovery.
  const listedRows = (ids: string[], previous?: ModelList) => {
    const known = new Map(previous?.models.map(row => [row.id, row]))
    return ids.map(id => known.get(id) ?? { id, kind: 'other' as const, capability: null, analysis: false, image: false })
  }

  const backfillModels = (connection: Connection, listing?: { models?: string[]; recommended?: Record<string, string[]> }) => {
    const ids = orderedIds(listing)
    if (ids.length) {
      setLists(old => {
        const models = listedRows(ids, old[connection.id])
        return { ...old, [connection.id]: mergeCustomList(connection, {
          models, source: 'live', preview: false, updated_at: Date.now(),
        }) }
      })
    }
    void discover(connection, true, 'manual')
  }

  const fetchModels = async (connection: Connection): Promise<FetchListResult> => {
    const version = (versions.current[connection.id] || 0) + 1
    versions.current[connection.id] = version
    setBusy(old => ({ ...old, [connection.id]: true }))
    try {
      const listing = await modelSettingsApi.fetchList(connection)
      if (!alive.current || versions.current[connection.id] !== version) return listing
      if (listing.ok || listing.success) {
        setLists(old => ({
          ...old,
          [connection.id]: mergeCustomList(connection, {
            models: listedRows(orderedIds(listing), old[connection.id]),
            source: listing.source === 'cache' || listing.source === 'catalog' ? listing.source : 'live',
            preview: false,
            updated_at: Date.now(),
          }),
        }))
        setListErrors(old => { const next = { ...old }; delete next[connection.id]; return next })
      } else {
        setListErrors(old => ({
          ...old,
          [connection.id]: t(listing.message_key || listing.hint_key || 'settings.providers.fetch_list_failed'),
        }))
      }
      return listing
    } catch (e) {
      if (alive.current && versions.current[connection.id] === version) {
        setListErrors(old => ({
          ...old,
          [connection.id]: t('settings.providers.fetch_list_failed'),
        }))
      }
      throw e
    } finally {
      if (alive.current && versions.current[connection.id] === version) setBusy(old => ({ ...old, [connection.id]: false }))
    }
  }

  const probe = async (
    connection: Connection,
    model: string,
    vision: boolean,
    role: Role,
    probeKind: 'quick' | 'trial' = 'quick',
    signal?: AbortSignal,
  ): Promise<ValidationResult> => {
    const payload = { ...connection, api_key: connection.api_key?.trim() ?? connection.api_key }
    tested.current.delete(connection.id)
    try {
      const result = await modelSettingsApi.test(payload, model, vision, role, probeKind, { signal })
      if (passed(result) && !signal?.aborted) {
        const base_url = logic.presetKey(connection) === 'compatible' && result.normalized_base_url
          ? result.normalized_base_url : connection.base_url
        tested.current.set(connection.id, probeSignature({ ...connection, base_url }, model, vision, role))
      }
      return result
    } catch (e) {
      const error = e as { code?: string; response?: { status?: number } } | null
      const status = error?.response?.status
      const errorType = status === 429 ? 'rate_limited'
        : status && status >= 500 && status <= 599 ? 'upstream_unavailable'
        : status === 401 ? 'invalid_key'
        : !status ? (error?.code === 'ECONNABORTED' || error?.code === 'ETIMEDOUT' ? 'timeout' : 'connection') : 'unknown'
      const desktop = typeof window !== 'undefined' && ('__TAURI_INTERNALS__' in window || '__TAURI__' in window)
      const emptyKey = !(connection.api_key || '').trim() && !connection.has_key
      // Telemetry-only fields; the user-facing error_type/hint above are unchanged.
      return { success: false, ok: false, result: isRetryableUpstreamError(errorType) ? 'transient' : 'failed', error_type: errorType, hint_key: hintKeyForUpstreamError(errorType),
        error_code: codeFromRequestError(e, { emptyKey, desktop }), http_status: typeof status === 'number' ? status : null }
    }
  }

  /** Validate, persist, and report the first blocking problem so the caller can scroll to it.
   * `patch` is merged first so a click can persist a choice made in the same turn as this save.
   * `base` is an already-built document (key guide) so save does not close over a stale render. */
  const save = async (patch?: Partial<ModelSettings>, base?: ModelSettings, checked?: { connectionId: string; list: ModelList }, validateConnections = placement !== 'settings_model'): Promise<{ ok: boolean; issue?: SaveIssue; validationFailed?: boolean }> => {
    const source = base ?? settings
    if (!source) return { ok: false }
    const current = patch ? { ...source, ...patch } : source
    if (!checked && (patch || base)) setSettings(current)
    const currentLists = checked ? { ...lists, [checked.connectionId]: checked.list } : lists
    const finish = beginExperience('provider_configuration_save', summary(current))
    const allowAccountOnly = placement === 'settings_model' && (!validateConnections || !current.analysis)
    const issue = logic.saveIssue(current, allowAccountOnly)
    if (issue) { finish('blocked', { reason: issue.reason, role: issue.role, error_code: 'validation' }); const text = issueText(issue); setError(text); message.error(text); return { ok: false, issue } }
    setSaving(true); setError('')
    try {
      let next = current
      let warned = ''
      const noticed: Array<{ id: string; status?: string; errorType?: string }> = []
      // The settings page saves preferences. Only the explicit connection/setup flow runs a probe.
      const targets = validateConnections ? logic.validationTargets(next) : []
      for (const { role, connection, model } of targets) {
        const vision = probeVision(next, role, currentLists)
        const signature = probeSignature(connection, model, vision, role)
        const previous = savedRef.current
        const oldConnection = previous && logic.connectionOf(previous, role)
        const savedSignature = previous && oldConnection?.validation_status === 'ok'
          ? probeSignature(oldConnection, previous[role]?.model || '', probeVision(previous, role, currentLists), role)
          : undefined
        if (connection.validation_status === 'ok' && signature === (tested.current.get(connection.id) ?? savedSignature)) continue
        const result = await probe(connection, model, vision, role)
        emitValidation(connection, result)
        next = logic.applyValidation(next, connection.id, result, model, role, vision)
        const row = next.connections.find(item => item.id === connection.id)
        if (row) noticed.push({ id: row.id, status: row.validation_status, errorType: row.validation_error_type })
        if (passed(result)) {
          const text = acceptWarning(connection.id, result)
          if (text) warned = text
          const normalized = { ...connection, base_url: result.normalized_base_url || connection.base_url }
          // Image/audio model ids carry no chat capability metadata.
          if (role === 'analysis' || role === 'vision') backfillModels(normalized, result)
          else void discover(normalized, true, 'manual')
        }
        else {
          const autoVisionMiss = role === 'analysis' && next.analysis_mode !== 'visual'
            && (result.error_type === 'vision_unsupported' || result.error_code === 'vision_unsupported')
          acceptWarning(connection.id, result)
          if (!autoVisionMiss) {
            setError(failureCopy(result, model))
            if (checked) { finish('failed', connectionTestFailure(result)); return { ok: false, validationFailed: true } }
          }
        }
        if (!checked) setSettings(next)
      }
      for (const connection of next.connections) {
        if (noticed.some(item => item.id === connection.id)) continue
        const previous = savedRef.current?.connections.find(item => item.id === connection.id)
        const keyChanged = (connection.api_key || '') !== (previous?.api_key || '')
        if (!keyChanged) continue
        if (connection.validation_status === 'failed' || connection.validation_status === 'transient') {
          noticed.push({ id: connection.id, status: connection.validation_status, errorType: connection.validation_error_type })
        }
      }
      const toast = saveToast(noticed)
      const value = await modelSettingsApi.save(logic.forSave(next), savedRef.current ? logic.forSave(savedRef.current) : undefined)
      setSettings(value); setDirty(false); setConflicted(false); autoCover.current = false
      loadedSignature.current = connectionSignature(value)
      finish('completed')
      tested.current.clear()
      savedRef.current = value
      if (toast.kind === 'invalid') message.error(`${t('settings.key_guide.invalid_saved')} ${validationCopy(toast.errorType)}`.trim())
      else if (toast.kind === 'failed') message.error(validationCopy(toast.errorType) || t('settings.key_guide.invalid_saved'))
      else if (toast.kind === 'unverified') {
        const warn = (message as { warning?: (text: string) => void }).warning
        const text = t('settings.key_guide.unverified')
        if (typeof warn === 'function') warn(text)
        else message.error(text)
      } else if (!checked) message.success(t('已保存'))
      if (warned) message.warning(warned)
      const failed = logic.hasFailedSelection(value)
      const visionFailed = logic.visionFollowLacksCapability(next, currentLists) || logic.visionFollowLacksCapability(value, currentLists)
      if (visionFailed && !failed) setError(t(VISION_HINT_KEY))
      // back to the failed project, if settings were opened from one (SETTINGS_SAVED_EVENT in studio/settingsReturn).
      if (value.analysis?.model && !failed && !visionFailed) notifySettingsSaved()
      return { ok: true, validationFailed: failed || visionFailed }
    } catch (e) {
      finish('failed', {}, e)
      const conflict = (e as { response?: { status?: number } })?.response?.status === 409
      setConflicted(conflict)
      setError(conflict ? t('设置已在另一处修改，请重新载入后再保存。') : errorText(e))
      return { ok: false }
    }
    finally { setSaving(false) }
  }

  // Discover, check access, then persist the complete document in one save.
  const configureProvider = async (connection: Connection, base = settings): Promise<{ ok: boolean; error?: string }> => {
    if (!base || matchingRef.current || saving) return { ok: false }
    matchingRef.current = true
    setMatching(true)
    setError('')
    try {
      const discovered = beginExperience('model_discovery', discoveryProperties(connection, 'manual'))
      const list = await modelSettingsApi.discover({ ...connection, custom_models: [] }, true).catch(e => {
        discovered('failed', {}, e)
        throw e
      })
      discovered('completed', { source: list.source, preview: !!list.preview, has_warning: !!list.warning, result_count: list.models.length })
      if (!alive.current) return { ok: false }
      let next = recommendProviderSetup(base, connection, list)
      // Some named providers permit chat but do not expose an account list. Probe one
      // analysis candidate before using it. A catalog preview never enables optional services.
      if (!next && list.preview && !connection.enabled_model_ids && getProvider(connection.provider)?.candidates.analysis.length) {
        const draft = { ...base, analysis: base.analysis?.connection_id === connection.id ? base.analysis : logic.cleanBinding(connection.id) }
        const binding = quickConnectPatch(draft)?.analysis || draft.analysis
        if (binding?.model && !isImageMarker(binding.model)) next = preserveFixedAssignments(base, syncFollowingCover(base, { ...base, analysis: binding }))
      }
      if (!next || (!next.analysis?.model && placement !== 'settings_model')) throw new Error(t('无法自动匹配剪辑模型。请检查密钥，或手动选择模型。'))
      if (requireCloudTranscription && next.transcription?.provider !== 'cloud') {
        throw new Error(t('连接支持语音识别的服务商后，即可继续导入。'))
      }
      const target = (['analysis', 'vision', 'transcription', 'cover'] as const).map(role => ({
        role, binding: next[role],
      })).find(({ binding }) => binding?.connection_id === connection.id && binding.model)
      if (!target?.binding) {
        // The account can still be saved when every available purpose is manually assigned elsewhere.
        if (placement === 'settings_model' && base.analysis?.model) {
          setLists(old => ({ ...old, [connection.id]: list }))
          return await save(undefined, next)
        }
        throw new Error(t('无法自动匹配剪辑模型。请检查密钥，或手动选择模型。'))
      }
      const vision = probeVision(next, target.role, { ...lists, [connection.id]: list })
      const value = await probe(connection, target.binding.model, vision, target.role)
      if (!alive.current) return { ok: false }
      emitValidation(connection, value)
      if (!passed(value)) throw new Error(failureCopy(value, target.binding.model))
      const verified = logic.applyValidation(next, connection.id, value, target.binding.model, target.role, vision)
      setLists(old => ({ ...old, [connection.id]: list }))
      const saved = await save(undefined, verified, { connectionId: connection.id, list })
      if (!saved.ok || saved.validationFailed) return { ok: false, error: saved.issue ? issueText(saved.issue) : t('保存失败，请重试') }
      const purposes = [
        [next.analysis, '精彩片段分析'], [next.vision, '画面理解'], [next.transcription, '语音转字幕'], [next.cover, '封面生成'],
      ] as const
      const labels = purposes.filter(([binding, label]) => binding?.connection_id === connection.id && (!list.preview || label === '精彩片段分析')).map(([, label]) => t(label))
      message.success(t('已配置：{{purposes}}', { purposes: labels.join(' · ') }))
      return { ok: true }
    } catch (e) {
      const text = errorText(e)
      setError(text)
      return { ok: false, error: text }
    } finally {
      matchingRef.current = false
      if (alive.current) setMatching(false)
    }
  }

  const validateCatalogConnection = async (connection: Connection, model: string) => {
    if (!settings || !connection.base_url.trim() || !model.trim()) return
    const version = versions.current[connection.id] || 0
    setTesting(true)
    try {
      const result = await probe(connection, model, false, 'analysis')
      if (!alive.current || (versions.current[connection.id] || 0) !== version) return
      emitValidation(connection, result)
      setSettings(old => old && logic.applyValidation(old, connection.id, result, model))
      setDirty(true)
      if (passed(result)) {
        const warn = acceptWarning(connection.id, result)
        if (warn) message.warning(warn)
        backfillModels(connection, result)
        void discover(connection, true, 'manual')
      } else acceptWarning(connection.id, result)
    } finally { setTesting(false) }
  }

  const cancelTrial = () => {
    trialAbortRef.current?.abort()
    trialAbortRef.current = null
    setTesting(false)
    setTestingKind(null)
  }

  const test = async (role: Role = 'analysis', probeKind: 'quick' | 'trial' = 'quick') => {
    const connection = settings && logic.connectionOf(settings, role)
    const binding = settings?.[role]
    if (!settings || !binding?.model || !connection || (role === 'transcription' && settings.transcription?.provider !== 'cloud')) return
    const capability = role === 'analysis' || role === 'vision' ? bindingCapability(settings[role], lists) : 'auto'
    const finish = beginExperience('provider_connection_test', { placement, provider: telemetryProvider(connection.provider), capability })
    trialAbortRef.current?.abort()
    const controller = new AbortController()
    trialAbortRef.current = controller
    setTesting(true)
    setTestingKind(probeKind)
    try {
      const vision = probeVision(settings, role, lists)
      const value = await probe(connection, binding.model, vision, role, role === 'analysis' ? probeKind : 'quick', controller.signal)
      emitValidation(connection, value)
      replace(logic.applyValidation(settings, connection.id, value, binding.model, role, vision))
      finish(passed(value) ? 'completed' : 'failed', { config_source: value.config_source, ...(passed(value) ? {} : connectionTestFailure(value)) })
      if (passed(value)) {
        const normalized = { ...connection, base_url: value.normalized_base_url || connection.base_url }
        if (role === 'analysis' || role === 'vision') backfillModels(normalized, value)
        else void discover(normalized, true, 'manual')
        message.success(t('连接正常'))
        const warn = acceptWarning(connection.id, value)
        if (warn) message.warning(warn)
        setError('')
      } else {
        acceptWarning(connection.id, value)
        const text = failureCopy(value, binding.model)
        setError(text)
        message.error(text)
      }
    } catch (e) {
      if ((e as { name?: string })?.name === 'CanceledError' || (e as { code?: string })?.code === 'ERR_CANCELED') {
        finish('failed', { reason: 'cancelled' })
      } else {
        finish('failed', {}, e); message.error(errorText(e))
      }
    }
    finally {
      if (trialAbortRef.current === controller) trialAbortRef.current = null
      setTesting(false)
      setTestingKind(null)
    }
  }


  const testCatalogProvider = async (
    presetId: string,
    draft?: Partial<Connection>,
    probeKind: 'quick' | 'trial' = 'quick',
  ) => {
    if (!settings) return
    const preset = catalogPreset(presetId)
    if (!preset) return
    const existing = draft?.id ? settings.connections.find(row => row.id === draft.id) : undefined
    const ensured = existing
      ? { settings, connection: existing }
      : ensureCatalogConnection(settings, preset)
    let next = existing && !settings.analysis && preset.capabilities.includes('language')
      ? assignAnalysis(settings, existing)
      : ensured.settings
    let connection = ensured.connection
    if (!connection) return
    if (!existing) {
      const patch: Partial<Connection> = { ...(draft || {}) }
      delete patch.id
      if (!(patch.base_url ?? connection.base_url)?.trim() && preset.base_url) {
        patch.base_url = preset.base_url
      }
      if (Object.keys(patch).length) {
        next = logic.editConnection(next, connection.id, patch)
        connection = next.connections.find(row => row.id === connection!.id) || connection
      }
    }
    const effectiveBaseUrl = (existing ? (draft?.base_url ?? connection.base_url) : connection.base_url).trim()
    if (!effectiveBaseUrl && preset.protocol !== 'local') {
      const text = t('请先填写接口地址。')
      setError(text)
      message.error(text)
      replace(next)
      return
    }
    if (!(connection.api_key || '').trim() && !connection.has_key && preset.auth === 'api_key') {
      const text = t('请先填写 API 密钥。')
      setError(text)
      message.error(text)
      replace(next)
      return
    }
    replace(next)
    const finish = beginExperience('provider_connection_test', {
      placement, provider: telemetryProvider(connection.provider), capability: 'auto',
    })
    trialAbortRef.current?.abort()
    const controller = new AbortController()
    trialAbortRef.current = controller
    setTesting(true)
    setTestingKind(probeKind)
    try {
      const active = next.analysis?.connection_id === connection.id
      let model = active ? next.analysis?.model : ''
      let available = lists
      if (!model) {
        try {
          const merged = mergeCustomList(connection, await modelSettingsApi.discover(connection, true))
          available = { ...lists, [connection.id]: merged }
          setLists(old => ({ ...old, [connection!.id]: merged }))
          model = pickRecommendedTestModel(connection, merged)
        } catch (e) {
          setListErrors(old => ({ ...old, [connection!.id]: errorText(e) }))
        }
        model ||= preset.candidates.analysis[0]
      }
      if (!model) {
        const text = t('请先选择模型')
        finish('blocked', { reason: 'model' })
        setError(text)
        message.error(text)
        return
      }
      const testedModel = t('settings.providers.test_model', { model })
      const vision = active && probeVision(next, 'analysis', available)
      const value = await probe(connection, model, vision, 'analysis', probeKind, controller.signal)
      if (controller.signal.aborted) return
      emitValidation(connection, value)
      const appliedBase = logic.applyValidation(settingsRef.current || next, connection.id, value, model, 'analysis', vision)
      const testedEntry = available[connection.id]?.models.find(row => row.id === model)
      const applied: ModelSettings = passed(value) && !appliedBase.analysis?.model
        ? {
            ...appliedBase,
            analysis: {
              connection_id: connection.id,
              model,
              capability: testedEntry?.capability === 'multimodal' || testedEntry?.capability === 'text' ? testedEntry.capability : 'auto',
              model_source: 'preset',
            },
          }
        : appliedBase
      replace(applied)
      finish(passed(value) ? 'completed' : 'failed', { config_source: value.config_source, ...(passed(value) ? {} : connectionTestFailure(value)) })
      if (passed(value)) {
        const normalized = { ...connection, base_url: value.normalized_base_url || connection.base_url }
        backfillModels(normalized, value)
        if (probeKind === 'trial' && value.trial_passed === false) {
          message.warning(testedModel + ' · ' + t('未通过试跑'))
        } else {
          message.success(testedModel + ' · ' + t('连接正常'))
        }
        const warn = acceptWarning(connection.id, value)
        if (warn) message.warning(warn)
        setError('')
      } else {
        acceptWarning(connection.id, value)
        const text = testedModel + ' · ' + failureCopy(value, model)
        setError(text)
        message.error(text)
      }
    } catch (e) {
      if ((e as { name?: string })?.name === 'AbortError' || controller.signal.aborted) return
      finish('failed', {}, e)
      message.error(errorText(e))
    } finally {
      if (trialAbortRef.current === controller) trialAbortRef.current = null
      setTesting(false)
      setTestingKind(null)
    }
  }

  const applyKeyGuide = async (request: KeyGuideRequest) => {
    const current = settingsRef.current
    if (!current) return { ok: false }
    const custom = request.providerId === CUSTOM_PROVIDER_ID
    const preset = custom ? undefined : getProvider(request.providerId)
    if (!custom && !preset) return { ok: false }
    const endpoints: GuideEndpoint[] = current.connections.map(connection => ({
      id: connection.id,
      providerId: connection.provider,
      baseUrl: connection.base_url || '',
      apiKey: connection.api_key,
      hasKey: !!connection.has_key,
    }))
    const plan = planPlacement({
      endpoints,
      providerId: request.providerId,
      apiKey: request.apiKey,
      baseUrl: request.baseUrl,
      overwrite: request.overwrite,
      officialBaseUrl: preset?.base_url || '',
    })
    if (plan.action === 'blocked') {
      setError(t('settings.key_guide.keep'))
      message.error(t('settings.key_guide.keep'))
      return { ok: false, blocked: true }
    }
    let next = current
    let connectionId = ''
    if (plan.action === 'create' && plan.custom) {
      // A first-run document has no analysis model. Bind a probe id so save can
      // check the key; the user can change the model afterwards.
      const draft = {
        ...emptyDraft(),
        name: plan.name,
        base_url: plan.baseUrl,
        api_key: plan.apiKey,
        ...(!current.analysis ? { models: [emptyOffer('gpt-4o-mini')] } : {}),
      }
      next = applyCustomProvider(current, draft)
      connectionId = next.connections[next.connections.length - 1]?.id || ''
    } else if (plan.action === 'create' && preset) {
      const draft = catalogDraftConnection(preset, crypto.randomUUID())
      if (!draft) return { ok: false }
      connectionId = draft.id
      const connection = { ...draft, api_key: plan.apiKey, has_key: true }
      next = { ...current, connections: [...current.connections, connection] }
      if (!next.analysis && preset.capabilities.includes('language')) next = assignAnalysis(next, connection)
    } else if (plan.action === 'unchanged') {
      connectionId = plan.connectionId
    } else if (plan.action === 'update') {
      connectionId = plan.connectionId
      const patch: Partial<Connection> = { api_key: plan.apiKey }
      if (plan.baseUrl) patch.base_url = plan.baseUrl
      next = logic.editConnection(current, plan.connectionId, patch)
    }
    const connection = next.connections.find(item => item.id === connectionId)
    if (connection && preset?.capabilities.includes('language') && (!next.analysis || next.analysis.connection_id === connection.id)
        && !next.analysis?.model) {
      const binding = logic.cleanBinding(connection.id)
      const model = request.model?.trim() || preset.default_model || preset.candidates.analysis[0]
      next = { ...next, analysis: { ...binding, model: model || '', model_source: request.model?.trim() ? 'user' : 'preset' } }
      if (!model) {
        try {
          const list = await modelSettingsApi.discover(connection, true)
          const matched = recommendProviderSetup(next, connection, list)
          if (matched?.analysis) next = { ...next, analysis: matched.analysis }
          setLists(old => ({ ...old, [connection.id]: list }))
        } catch {
          // Keep the draft editable. The normal save guard asks for a manual model ID.
        }
      }
    }
    const bound = logic.validationTargets(next).some(item => item.connection.id === connectionId)
    if (connection && !bound) {
      const model = preset?.default_model || preset?.candidates?.analysis?.[0] || request.model?.trim() || (custom ? 'gpt-4o-mini' : '')
      if (model) {
        const result = await probe(connection, model, false, 'analysis')
        emitValidation(connection, result)
        next = logic.applyValidation(next, connection.id, result, model)
        if (!passed(result)) setError(failureCopy(result, model))
      }
    }
    const selectId = custom ? `custom:${connectionId}` : request.providerId
    if (connectionId && selectId) stagePendingSelect(selectId)
    settingsRef.current = next
    replace(next)
    const outcome = await save(undefined, next, undefined, true)
    return { ok: outcome.ok, blocked: false, connectionId }
  }
  const applyRef = useRef(applyKeyGuide)
  applyRef.current = applyKeyGuide
  useEffect(() => registerKeyGuideApplier(request => applyRef.current(request)), [])
  useEffect(() => {
    if (!settings) return
    const request = takePendingRequest()
    if (request) void applyRef.current(request)
  }, [settings])

  const main = settings ? logic.mainConnection(settings) : undefined
  return {
    settings, lists, busy, listErrors, dirty, dirtyRef, conflicted, saving: saving || matching, testing, error, configureProvider, testWarning, setError, main, keyHints,
    load, discover, fetchModels, update, editConnection, declareModel, chooseProvider, addCustomProvider, ensureCatalogProvider,
    assignAnalysisConnection, validateCatalogConnection, testCatalogProvider, selectLocalAsrProvider, setTranscriptionLocal,
    setCoverSeparate, setCoverEnabled, setCoverModel, setVisual, clearConnectionKey, removeConnection, save, test, cancelTrial,
    testingKind, lastTrialByConnection,
  }
}
