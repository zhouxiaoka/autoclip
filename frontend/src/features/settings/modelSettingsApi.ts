import api from '../../services/api'

export type Capability = 'auto' | 'multimodal' | 'text'
export interface Connection {
  id: string
  name: string
  provider: string
  base_url: string
  api_key?: string | null
  has_key?: boolean
  api_key_masked?: string
  image_api: 'auto' | 'openai' | 'seedream' | 'dashscope' | 'fal'
  image_base_url: string
}
export interface Assignment { connection_id: string; model: string; capability: Capability }
export interface ModelSettings {
  version: 1
  saved?: boolean
  connections: Connection[]
  analysis: Assignment | null
  vision: Assignment | null
  cover: Assignment | null
  transcription?: { provider: 'whisper_local' | 'sensevoice_local' | 'cloud'; model: string; connection_id?: string; capability?: Capability } | null
  cover_enabled: boolean
  allow_send_frame: boolean
  analysis_mode: 'auto' | 'subtitle' | 'visual'
  allow_visual_screening: boolean
  chunk_size: number
  min_score_threshold: number
  max_clips_per_collection: number
}
export interface ModelEntry { id: string; capability: 'multimodal' | 'text' | null; capability_source?: string; analysis: boolean; image: boolean; asr?: boolean; asr_supported?: boolean; asr_preview?: boolean; asr_note?: string | null }
export interface ModelList { models: ModelEntry[]; source: 'live' | 'cache' | 'catalog'; preview?: boolean; updated_at: number | null; warning?: string }
export const modelSettingsApi = {
  get: () => api.get<unknown, ModelSettings>('/settings/ai-models'),
  save: (value: ModelSettings) => api.put<unknown, ModelSettings>('/settings/ai-models', value),
  discover: (connection: Connection, refresh = false) => api.post<unknown, ModelList>('/settings/ai-models/discover', { connection, refresh }),
  test: (connection: Connection, model: string, vision = false) => api.post<unknown, { success?: boolean; ok?: boolean }>('/settings/ai-models/test', { connection, model, vision }),
}

export function bindingCapability(binding: Assignment | null, lists: Record<string, ModelList>): Capability {
  if (!binding) return 'auto'
  return binding.capability !== 'auto' ? binding.capability : lists[binding.connection_id]?.models.find(m => m.id === binding.model)?.capability || 'auto'
}
