/**
 * Pure step for the import-zone setup card: a chosen provider with an empty
 * analysis model gets the catalog's first analysis candidate so save can probe.
 * No React, no network.
 */
import type { ModelSettings } from './modelSettingsApi'
import { mainConnection, presetKey } from './modelSettingsLogic'
import { analysisCandidates } from './providerPresets'

export function quickConnectPatch(settings: ModelSettings): Partial<ModelSettings> | undefined {
  const main = mainConnection(settings)
  if (!main || !settings.analysis || settings.analysis.model) return undefined
  const model = analysisCandidates(presetKey(main))[0] || ''
  if (!model) return undefined
  return { analysis: { ...settings.analysis, model, model_source: 'preset' } }
}
