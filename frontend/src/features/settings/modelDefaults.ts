import { endpointProviderReady } from './endpointProvider'
import type { Connection, ModelEntry, ModelSettings } from './modelSettingsApi'
import { analysisCandidates, asrCandidates, imageCandidates, visionCandidates } from './providerPresets'

// Preference order only: select a recommendation from the provider's actual list.
// Never substitute an existing explicit choice when a catalog refreshes.
// Order comes from backend/presets/provider_presets.json candidates.
export function defaultModel(provider: string, models: ModelEntry[], image = false, purpose: 'analysis' | 'vision' = 'analysis'): string {
  const eligible = models.filter(m => image ? m.image : m.analysis)
  if (image && provider === 'infistar') return eligible.find(m => m.id === 'qwen-image-plus')?.id || eligible[0]?.id || ''
  const vision = purpose === 'vision' ? visionCandidates(provider) : []
  const preferred = image ? imageCandidates(provider) : (vision.length ? vision : analysisCandidates(provider))
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

/** Same rule as the backend: explicit flag, else the pre-flag meaning (cover on the analysis connection). */
export function coverFollowsAnalysis(s: ModelSettings): boolean {
  if (typeof s.cover_follows_analysis === 'boolean') return s.cover_follows_analysis
  return !!s.cover && !!s.analysis && s.cover.connection_id === s.analysis.connection_id
}

/**
 * Call after analysis moved. A following cover moves with it (image model re-recommended for the
 * new connection); an independent cover keeps its connection, whatever its model_source.
 */
export function syncFollowingCover(before: ModelSettings, next: ModelSettings): ModelSettings {
  const follow = coverFollowsAnalysis(before)
  const value: ModelSettings = { ...next, cover_follows_analysis: follow }
  if (follow && value.cover && value.analysis && value.cover.connection_id !== value.analysis.connection_id) {
    value.cover = { connection_id: value.analysis.connection_id, model: '', capability: 'auto', model_source: 'preset' }
  }
  return value
}

export function applyModelDefaults(settings: ModelSettings, connection: Connection, models: ModelEntry[], _autoCover: boolean): ModelSettings {
  if (!endpointProviderReady(connection)) return settings
  const value = { ...settings }
  for (const role of ['analysis', 'vision', 'cover'] as const) {
    const binding = value[role]
    if (binding?.connection_id !== connection.id || binding.model) continue
    const eligible = role === 'cover' ? models : analysisModels(models, role === 'vision' ? 'visual' : settings.analysis_mode)
    const model = defaultModel(connection.provider, eligible, role === 'cover', role === 'vision' ? 'vision' : 'analysis')
    if (model) value[role] = { ...binding, model, model_source: binding.model_source || 'preset' }
  }
  // AI covers switched on by the user before a model list arrived: fill the recommended image model.
  // Never switched on automatically: without the user's choice, covers are designed locally.
  if (value.cover_enabled && !value.cover && value.analysis?.connection_id === connection.id) {
    const model = defaultModel(connection.provider, models, true)
    if (model) { value.cover = { connection_id: connection.id, model, capability: 'auto', model_source: 'preset' }; value.cover_follows_analysis = true }
  }
  if (value.transcription?.provider === 'cloud' && value.transcription.connection_id === connection.id && !value.transcription.model) {
    const fitting = models.filter(m => m.asr && m.asr_supported && !m.asr_preview)
    const model = asrCandidates(connection.provider).find(id => fitting.some(m => m.id === id)) || fitting[0]?.id
    if (model) value.transcription = { ...value.transcription, model, model_source: value.transcription.model_source || 'preset' }
  }
  return value
}
