/**
 * Shared connect-and-save used by the first-run overlay and the import setup card.
 * A save in one instance reloads the other; dismissing the overlay does not.
 */
import { useEffect, useRef } from 'react'
import type { Placement } from '../../analytics/experience'
import { SETTINGS_SAVED_EVENT } from '../studio/settingsReturn'
import { mainConnection } from './modelSettingsLogic'
import type { ProviderKey } from './providers'
import { quickConnectPatch } from './quickConnect'
import { useModelSettings } from './useModelSettings'

export function useQuickConnect(placement: Placement = 'home_setup') {
  const model = useModelSettings(placement)
  const ownSave = useRef(false)
  const loadRef = useRef(model.load)
  loadRef.current = model.load
  useEffect(() => {
    const onSaved = () => { if (!ownSave.current) void loadRef.current() }
    window.addEventListener(SETTINGS_SAVED_EVENT, onSaved)
    return () => window.removeEventListener(SETTINGS_SAVED_EVENT, onSaved)
  }, [])
  const save: typeof model.save = async (patch, base) => {
    ownSave.current = true
    try { return await model.save(patch, base) }
    finally { ownSave.current = false }
  }
  const selectProvider = (provider: ProviderKey) => model.chooseProvider('analysis', provider)
  const setKey = (value: string) => {
    const settings = model.settings
    const main = settings && mainConnection(settings)
    if (!settings || !main) return
    model.editConnection(main, { api_key: value })
  }
  const connect = async () => {
    const settings = model.settings
    if (!settings) return { ok: false as const }
    return save(quickConnectPatch(settings))
  }
  return { ...model, save, selectProvider, setKey, connect }
}
