import type { Connection, ModelEntry, ModelSettings } from './modelSettingsApi'
import { analysisCandidates, imageCandidates } from './providerPresets'

// Preference order only: select a recommendation from the provider's actual list.
// Never substitute an existing explicit choice when a catalog refreshes.
// Order comes from presets/provider_presets.json candidates.
export function defaultModel(provider: string, models: ModelEntry[], image = false): string {
  const eligible = models.filter(m => image ? m.image : m.analysis)
  if (image && provider === 'infistar') return eligible.find(m => m.id === 'qwen-image-plus')?.id || eligible[0]?.id || ''
  const preferred = image ? imageCandidates(provider) : analysisCandidates(provider)
  if (image) return preferred.length
    ? preferred.find(id => eligible.some(m => m.id === id)) || ''
    : eligible[0]?.id || ''
  return preferred.find(id => eligible.some(m => m.id === id))
    || eligible.find(m => m.capability === 'multimodal')?.id || eligible[0]?.id || ''
}

export function analysisModels(models: ModelEntry[], mode: ModelSettings['analysis_mode']): ModelEntry[] {
  // 'auto' is smart selection: a text-only model simply analyses subtitles, so it stays eligible.
  // Only an explicit 'visual' route requires a multimodal model.
  return models.filter(m => m.analysis && (mode !== 'visual' || m.capability === 'multimodal'))
}

export function applyModelDefaults(settings: ModelSettings, connection: Connection, models: ModelEntry[], _autoCover: boolean): ModelSettings {
  const value = { ...settings }
  for (const role of ['analysis', 'vision', 'cover'] as const) {
    const binding = value[role]
    if (binding?.connection_id !== connection.id || binding.model) continue
    const eligible = role === 'cover' ? models : analysisModels(models, role === 'vision' ? 'visual' : settings.analysis_mode)
    const model = defaultModel(connection.provider, eligible, role === 'cover')
    if (model) value[role] = { ...binding, model, model_source: binding.model_source || 'preset' }
  }
  // AI covers switched on by the user before a model list arrived: fill the recommended image model.
  // Never switched on automatically: without the user's choice, covers are designed locally.
  if (value.cover_enabled && !value.cover && value.analysis?.connection_id === connection.id) {
    const model = defaultModel(connection.provider, models, true)
    if (model) value.cover = { connection_id: connection.id, model, capability: 'auto', model_source: 'preset' }
  }
  if (value.transcription?.provider === 'cloud' && value.transcription.connection_id === connection.id && !value.transcription.model) {
    const model = models.find(m => m.asr && m.asr_supported)?.id
    if (model) value.transcription = { ...value.transcription, model, model_source: value.transcription.model_source || 'preset' }
  }
  return value
}
