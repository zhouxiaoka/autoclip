import { useEffect, useRef, useState } from 'react'
import { message } from 'antd'
import { t } from '../../i18n'
import { errorText } from '../studio/api'
import { trackApiKeyConfigured } from '../../analytics/events'
import { PROVIDERS, type ProviderKey } from './providers'
import { bindingCapability, modelSettingsApi, type Connection, type ModelList, type ModelSettings } from './modelSettingsApi'
import { applyModelDefaults } from './modelDefaults'
import * as logic from './modelSettingsLogic'
import type { Role, SaveIssue } from './modelSettingsLogic'

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
export function useModelSettings() {
  const [settings, setSettings] = useState<ModelSettings | null>(null)
  const [lists, setLists] = useState<Record<string, ModelList>>({})
  const [busy, setBusy] = useState<Record<string, boolean>>({})
  const [listErrors, setListErrors] = useState<Record<string, string>>({})
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [error, setError] = useState('')
  const versions = useRef<Record<string, number>>({})
  const alive = useRef(true)
  // First run only: the recommended image model turns AI covers on. Any explicit cover choice ends it.
  const autoCover = useRef(false)

  const update = (patch: Partial<ModelSettings>) => {
    setSettings(old => old ? { ...old, ...patch } : old)
    setDirty(true)
  }
  const replace = (next: ModelSettings) => { setSettings(next); setDirty(true); setError('') }

  const discover = async (connection: Connection, refresh = false) => {
    if (connection.provider === 'compatible' && !connection.base_url) return
    const version = (versions.current[connection.id] || 0) + 1
    versions.current[connection.id] = version
    setBusy(old => ({ ...old, [connection.id]: true }))
    try {
      const result = await modelSettingsApi.discover(connection, refresh)
      if (!alive.current || versions.current[connection.id] !== version) return
      setLists(old => ({ ...old, [connection.id]: result }))
      setListErrors(old => { const next = { ...old }; delete next[connection.id]; return next })
      setSettings(old => old && !result.preview ? applyModelDefaults(old, connection, result.models, autoCover.current) : old)
    } catch (e) {
      if (alive.current && versions.current[connection.id] === version) setListErrors(old => ({ ...old, [connection.id]: errorText(e) }))
    } finally {
      if (alive.current && versions.current[connection.id] === version) setBusy(old => ({ ...old, [connection.id]: false }))
    }
  }

  const load = async () => {
    setError('')
    try {
      const value = logic.prepareLoaded(await modelSettingsApi.get())
      if (!alive.current) return
      autoCover.current = !value.saved
      setSettings(value)
      value.connections.forEach(c => { void discover(c) })
    } catch (e) { if (alive.current) setError(errorText(e)) }
  }
  useEffect(() => { alive.current = true; void load(); return () => { alive.current = false } }, [])

  const signature = JSON.stringify(settings?.connections.map(c => [c.id, c.provider, c.base_url, c.api_key, c.image_base_url]))
  useEffect(() => {
    if (!settings) return
    const timer = window.setTimeout(() => settings.connections.forEach(c => { void discover(c) }), 650)
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
    void discover(result.connection)
  }
  const setTranscriptionLocal = (model: string) => update({ transcription: { provider: 'whisper_local', model } })
  const setCoverSeparate = (separate: boolean) => { if (settings) replace(logic.setCoverSeparate(settings, separate, lists)) }
  const setCoverEnabled = (enabled: boolean) => { autoCover.current = false; if (settings) replace(logic.setCoverEnabled(settings, enabled, lists)) }
  const setCoverModel = (connectionId: string, model: string) => { autoCover.current = false; update({ cover_enabled: true, cover: { ...logic.cleanBinding(connectionId), model } }) }
  const setVisual = (enabled: boolean) => { if (settings) replace(logic.setVisual(settings, enabled)) }

  /** Validate, persist, and report the first blocking problem so the caller can scroll to it. */
  const save = async (): Promise<{ ok: boolean; issue?: SaveIssue }> => {
    if (!settings) return { ok: false }
    const effective = logic.coverFallback(settings, lists)
    const issue = logic.saveIssue(effective)
    if (issue) { const text = issueText(issue); setError(text); message.error(text); return { ok: false, issue } }
    setSaving(true); setError('')
    try {
      const value = await modelSettingsApi.save(logic.forSave(effective))
      setSettings(value); setDirty(false); autoCover.current = false
      value.connections.forEach(c => trackApiKeyConfigured({ provider: c.provider, hasKey: !!c.has_key || !!PROVIDERS[c.provider as ProviderKey]?.local }))
      message.success(t('已保存'))
      return { ok: true }
    } catch (e) { setError(errorText(e)); return { ok: false } }
    finally { setSaving(false) }
  }

  const test = async () => {
    const main = settings && logic.mainConnection(settings)
    if (!settings?.analysis?.model || !main) return
    setTesting(true)
    try {
      const vision = settings.analysis_mode !== 'subtitle' && bindingCapability(settings.analysis, lists) === 'multimodal'
      const value = await modelSettingsApi.test(main, settings.analysis.model, vision)
      if (value.success || value.ok) message.success(t('连接正常'))
      else message.error(t('连接测试失败，请检查接口、密钥和模型'))
    } catch (e) { message.error(errorText(e)) }
    finally { setTesting(false) }
  }

  const main = settings ? logic.mainConnection(settings) : undefined
  return {
    settings, lists, busy, listErrors, dirty, saving, testing, error, setError, main,
    load, discover, update, editConnection, chooseProvider, setTranscriptionLocal,
    setCoverSeparate, setCoverEnabled, setCoverModel, setVisual, save, test,
  }
}
