import { useEffect, useRef, useState } from 'react'
import { message } from 'antd'
import { t } from '../../i18n'
import { errorText } from '../studio/api'
import { beginExperience, trackProviderValidation, type Placement } from '../../analytics/experience'
import { hintKeyForUpstreamError } from '../../analytics/successRateContract'
import { PROVIDERS, type ProviderKey } from './providers'
import { bindingCapability, modelSettingsApi, type Connection, type FetchListResult, type ModelList, type ModelSettings } from './modelSettingsApi'
import { applyModelDefaults } from './modelDefaults'
import { slotTelemetry } from './defaultModelSlots'
import * as logic from './modelSettingsLogic'
import { assignAnalysis, ensureCatalogConnection, selectLocalAsr, type LocalAsrId } from './providerCatalogView'
import { getProvider } from './providerPresets'
import type { Role, SaveIssue } from './modelSettingsLogic'
import { passed, telemetryHost, validationCopy, VISION_HINT_KEY, type ValidationResult } from './providerAccess'
import { applyCustomProvider, mergeCustomList, type CustomProviderDraft } from './customProvider'

export const roleLabel = (role: Role) =>
  ({ analysis: t('模型'), vision: t('画面理解模型'), cover: t('生图模型'), transcription: t('转写模型') })[role]

export const issueText = (issue: SaveIssue) =>
  issue.reason === 'provider' ? t('请先选择一家 AI 服务')
    : `${roleLabel(issue.role)}：${issue.reason === 'model' ? t('请先选择模型') : t('请填写 API Key')}`

export type ModelSettingsStore = ReturnType<typeof useModelSettings>

/**
 * One editable copy of the AI model document, shared by the settings page and the first-run card.
 * Editing a key or address triggers one debounced discovery; recommendations fill empty slots only.
 */
export function useModelSettings(placement: Placement = 'settings_model') {
  const [settings, setSettings] = useState<ModelSettings | null>(null)
  const [lists, setLists] = useState<Record<string, ModelList>>({})
  const [busy, setBusy] = useState<Record<string, boolean>>({})
  const [listErrors, setListErrors] = useState<Record<string, string>>({})
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [error, setError] = useState('')
  const [keyHints, setKeyHints] = useState<Record<string, string>>({})
  const versions = useRef<Record<string, number>>({})
  const alive = useRef(true)
  // First run only: the recommended image model turns AI covers on. Any explicit cover choice ends it.
  const autoCover = useRef(false)
  const settingsRef = useRef(settings)
  settingsRef.current = settings
  const savedRef = useRef<ModelSettings | null>(null)
  const summary = (value: ModelSettings) => ({
    placement, provider: logic.mainConnection(value)?.provider || 'other',
    changed_connections: JSON.stringify(savedRef.current?.connections) !== JSON.stringify(value.connections), mode: value.saved ? 'update' : 'initial', analysis_mode: value.analysis_mode,
    analysis_configured: !!value.analysis?.model, vision_configured: !!value.vision?.model,
    cover_configured: !!value.cover?.model, transcription_configured: !!value.transcription?.model,
    transcription_mode: value.transcription?.provider || 'unknown', cover_mode: value.cover_enabled ? 'ai' : 'frame',
    cover_separate: !!value.cover && value.cover.connection_id !== value.analysis?.connection_id,
    ...slotTelemetry(value, lists),
    ...Object.fromEntries(['analysis', 'vision', 'cover', 'transcription'].map(role => [
      `changed_${role}`, JSON.stringify(savedRef.current?.[role as Role]) !== JSON.stringify(value[role as Role]),
    ])),
  })

  const update = (patch: Partial<ModelSettings>) => {
    setSettings(old => old ? { ...old, ...patch } : old)
    setDirty(true)
  }
  const replace = (next: ModelSettings) => { setSettings(next); setDirty(true); setError('') }

  const discover = async (connection: Connection, refresh = false, trigger: 'load' | 'edit' | 'provider_change' | 'manual' = 'manual') => {
    if (connection.provider === 'compatible' && !connection.base_url) return
    const finish = beginExperience('model_discovery', { placement, provider: PROVIDERS[connection.provider as ProviderKey] ? connection.provider : 'other', trigger })
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
    const finish = beginExperience('model_settings_load', { placement })
    setError('')
    try {
      const value = logic.prepareLoaded(await modelSettingsApi.get())
      if (!alive.current) return
      finish('completed')
      savedRef.current = value
      autoCover.current = !value.saved
      setSettings(value)
      setLists(old => {
        const next = { ...old }
        value.connections.forEach(connection => {
          if (connection.custom_models?.length) next[connection.id] = mergeCustomList(connection, next[connection.id])
        })
        return next
      })
      value.connections.forEach(c => { void discover(c, false, 'load') })
    } catch (e) { if (alive.current) { finish('failed', {}, e); setError(errorText(e)) } }
  }
  useEffect(() => { alive.current = true; void load(); return () => { alive.current = false } }, [])

  const signature = JSON.stringify(settings?.connections.map(c => [c.id, c.provider, c.base_url, c.api_key, c.image_base_url]))
  useEffect(() => {
    if (!settings) return
    const timer = window.setTimeout(() => settings.connections.forEach(c => { void discover(c, false, 'edit') }), 650)
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
    update(logic.editConnection(settings, connection.id, patch))
    setLists(old => { const next = { ...old }; delete next[connection.id]; return next })
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
  const setCoverModel = (connectionId: string, model: string) => { autoCover.current = false; update({ cover_enabled: true, cover: { ...logic.cleanBinding(connectionId), model, model_source: 'user' } }) }
  const setVisual = (enabled: boolean) => { if (settings) replace(logic.setVisual(settings, enabled)) }
  const addCustomProvider = (draft: CustomProviderDraft) => {
    if (!settings) return
    const next = applyCustomProvider(settings, draft)
    const connection = next.connections[next.connections.length - 1]
    replace(next)
    if (connection) setLists(old => ({ ...old, [connection.id]: mergeCustomList(connection) }))
  }

  const emitValidation = (connection: Connection, result: ValidationResult) => {
    const provider = PROVIDERS[connection.provider as ProviderKey] ? connection.provider : 'other'
    trackProviderValidation({
      provider,
      base_url_host: result.base_url_host || telemetryHost(connection.base_url),
      result: passed(result) ? 'success' : 'failed',
      ...(passed(result) ? {} : { upstream_error_type: result.error_type || 'unknown' }),
    })
    if (result.key_hint) setKeyHints(old => ({ ...old, [connection.id]: result.key_hint as string }))
  }

  const orderedIds = (listing?: { models?: string[]; recommended?: Record<string, string[]> }) => {
    const analysis = listing?.recommended?.analysis || []
    const live = listing?.models || []
    return analysis.length ? [...analysis, ...live.filter(id => !analysis.includes(id))] : live
  }

  const backfillModels = (connection: Connection, listing?: { models?: string[]; recommended?: Record<string, string[]> }) => {
    const ids = orderedIds(listing)
    if (ids.length) {
      setLists(old => ({
        ...old,
        [connection.id]: mergeCustomList(connection, {
          models: ids.map(id => ({ id, capability: null, analysis: true, image: false })),
          source: 'live', preview: false, updated_at: Date.now(),
        }),
      }))
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
            models: orderedIds(listing).map(id => ({ id, capability: null, analysis: true, image: false })),
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

  const probe = async (connection: Connection, model: string, vision: boolean, role: Role): Promise<ValidationResult> => {
    const payload = { ...connection, api_key: connection.api_key?.trim() ?? connection.api_key }
    try {
      return await modelSettingsApi.test(payload, model, vision, role)
    } catch {
      return { success: false, ok: false, result: 'failed', error_type: 'unknown', hint_key: hintKeyForUpstreamError('unknown') }
    }
  }

  /** Validate, persist, and report the first blocking problem so the caller can scroll to it. */
  const save = async (): Promise<{ ok: boolean; issue?: SaveIssue; validationFailed?: boolean }> => {
    if (!settings) return { ok: false }
    const effective = logic.coverFallback(settings, lists)
    const finish = beginExperience('provider_configuration_save', summary(effective))
    const issue = logic.saveIssue(effective)
    if (issue) { finish('blocked', { reason: issue.reason, role: issue.role, error_code: 'validation' }); const text = issueText(issue); setError(text); message.error(text); return { ok: false, issue } }
    setSaving(true); setError('')
    try {
      let next = effective
      for (const { role, connection, model } of logic.validationTargets(next)) {
        const modelChanged = savedRef.current?.[role]?.model !== next[role]?.model
          || savedRef.current?.[role]?.connection_id !== connection.id
        if (connection.validation_status === 'ok' && !modelChanged) continue
        const vision = role === 'vision' || (role === 'analysis' && next.analysis_mode !== 'subtitle' && bindingCapability(next.analysis, lists) === 'multimodal')
        const result = await probe(connection, model, vision, role)
        emitValidation(connection, result)
        next = logic.applyValidation(next, connection.id, result)
        if (passed(result)) {
          const normalized = { ...connection, base_url: result.normalized_base_url || connection.base_url }
          // Image/audio model ids carry no chat capability metadata.
          if (role === 'analysis' || role === 'vision') backfillModels(normalized, result)
          else void discover(normalized, true, 'manual')
        }
        else setError(validationCopy(result.error_type, result.hint_key))
        setSettings(next)
      }
      const value = await modelSettingsApi.save(logic.forSave(next))
      setSettings(value); setDirty(false); autoCover.current = false
      finish('completed')
      savedRef.current = value
      message.success(t('已保存'))
      const failed = [value, next].some(s => logic.validationTargets(s).some(({ connection }) => connection.validation_status === 'failed'))
      const visionFailed = logic.visionFollowLacksCapability(next, lists) || logic.visionFollowLacksCapability(value, lists)
      if (visionFailed && !failed) setError(t(VISION_HINT_KEY))
      return { ok: true, validationFailed: failed || visionFailed }
    } catch (e) { finish('failed', {}, e); setError(errorText(e)); return { ok: false } }
    finally { setSaving(false) }
  }

  const validateCatalogConnection = async (connection: Connection, model: string) => {
    if (!settings || !connection.base_url.trim() || !model.trim()) return
    const version = versions.current[connection.id] || 0
    setTesting(true)
    try {
      const result = await probe(connection, model, false, 'analysis')
      if (!alive.current || (versions.current[connection.id] || 0) !== version) return
      emitValidation(connection, result)
      setSettings(old => old && logic.applyValidation(old, connection.id, result))
      setDirty(true)
      if (passed(result)) {
        backfillModels(connection, result)
        void discover(connection, true, 'manual')
      }
    } finally { setTesting(false) }
  }

  const test = async (role: Role = 'analysis') => {
    const connection = settings && logic.connectionOf(settings, role)
    const binding = settings?.[role]
    if (!settings || !binding?.model || !connection || (role === 'transcription' && settings.transcription?.provider !== 'cloud')) return
    const capability = role === 'analysis' || role === 'vision' ? bindingCapability(settings[role], lists) : 'auto'
    const finish = beginExperience('provider_connection_test', { placement, provider: PROVIDERS[connection.provider as ProviderKey] ? connection.provider : 'other', capability })
    setTesting(true)
    try {
      const vision = role === 'vision' || (role === 'analysis' && settings.analysis_mode !== 'subtitle' && capability === 'multimodal')
      const value = await probe(connection, binding.model, vision, role)
      emitValidation(connection, value)
      replace(logic.applyValidation(settings, connection.id, value))
      finish(passed(value) ? 'completed' : 'failed')
      if (passed(value)) {
        const normalized = { ...connection, base_url: value.normalized_base_url || connection.base_url }
        if (role === 'analysis' || role === 'vision') backfillModels(normalized, value)
        else void discover(normalized, true, 'manual')
        message.success(t('连接正常'))
        setError('')
      } else {
        const text = validationCopy(value.error_type, value.hint_key)
        setError(text)
        message.error(text)
      }
    } catch (e) { finish('failed', {}, e); message.error(errorText(e)) }
    finally { setTesting(false) }
  }

  const main = settings ? logic.mainConnection(settings) : undefined
  return {
    settings, lists, busy, listErrors, dirty, saving, testing, error, setError, main, keyHints,
    load, discover, fetchModels, update, editConnection, chooseProvider, addCustomProvider, ensureCatalogProvider,
    assignAnalysisConnection, validateCatalogConnection, selectLocalAsrProvider, setTranscriptionLocal,
    setCoverSeparate, setCoverEnabled, setCoverModel, setVisual, save, test,
  }
}
