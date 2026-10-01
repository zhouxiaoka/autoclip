import type { Connection, ModelEntry, ModelSettings } from './modelSettingsApi'

// Preference order only: select a recommendation from the provider's actual list.
// Never substitute an existing explicit choice when a catalog refreshes.
const PREFERRED: Record<string, string[]> = {
  dashscope: ['qwen3.8-flash', 'qwen3.8-max', 'qwen-vl-plus', 'qwen-plus'],
  openai: ['gpt-5-mini', 'gpt-4o-mini'],
  gemini: ['gemini-3.8-flash', 'gemini-2.5-flash'],
  seed: ['doubao-seed-2-1-lite-260915'],
  deepseek: ['deepseek-flash'],
  kimi: ['kimi-k2.6', 'kimi-k3'],
  glm: ['glm-5.3'], grok: ['grok-4.6'],
}
const IMAGE_PREFERRED: Record<string, string[]> = {
  dashscope: ['qwen-image-2.0', 'wan2.7-image', 'wanx2.1-t2i-turbo', 'wanx2.1-t2i-plus'],
  openai: ['gpt-image-2.5-flare', 'gpt-image-2', 'gpt-image-1', 'dall-e-3'],
  seed: ['doubao-seedream-5-0-flash-260915', 'doubao-seedream-5-0-pro-260628', 'doubao-seedream-4-0-20260415', 'doubao-seedream-5-0-260128'],
}
export function defaultModel(provider: string, models: ModelEntry[], image = false): string {
  const eligible = models.filter(m => image ? m.image : m.analysis)
  if (image && provider === 'infistar') return eligible.find(m => m.id === 'qwen-image-plus')?.id || eligible[0]?.id || ''
  if (image) return IMAGE_PREFERRED[provider]
    ? IMAGE_PREFERRED[provider].find(id => eligible.some(m => m.id === id)) || ''
    : eligible[0]?.id || ''
  return PREFERRED[provider]?.find(id => eligible.some(m => m.id === id))
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
    if (model) value[role] = { ...binding, model }
  }
  // AI covers switched on by the user before a model list arrived: fill the recommended image model.
  // Never switched on automatically: without the user's choice, covers are designed locally.
  if (value.cover_enabled && !value.cover && value.analysis?.connection_id === connection.id) {
    const model = defaultModel(connection.provider, models, true)
    if (model) value.cover = { connection_id: connection.id, model, capability: 'auto' }
  }
  if (value.transcription?.provider === 'cloud' && value.transcription.connection_id === connection.id && !value.transcription.model) {
    const model = models.find(m => m.asr && m.asr_supported)?.id
    if (model) value.transcription = { ...value.transcription, model }
  }
  return value
}
