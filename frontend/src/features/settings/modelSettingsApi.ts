import api from '../../services/api'
import type { ValidationResult } from './providerAccess'

import type { CustomModelOffer } from './customProvider'

export type Capability = 'auto' | 'multimodal' | 'text'
export type Source = 'preset' | 'user'
export type ModelSource = Source
export interface Connection {
  id: string
  name: string
  provider: string
  catalog_provider_id?: string
  base_url: string
  api_key?: string | null
  has_key?: boolean
  api_key_masked?: string
  image_api: 'auto' | 'openai' | 'seedream' | 'dashscope' | 'fal'
  image_base_url: string
  validation_status?: 'ok' | 'failed' | 'unchecked' | 'transient'
  validation_error_type?: string
  base_url_source?: Source
  preset_version?: number
  custom_models?: CustomModelOffer[]
  enabled_model_ids?: string[] | null
}
export interface Assignment { connection_id: string; model: string; capability: Capability; model_source?: Source }
export interface ModelSettings {
  version: 1
  saved?: boolean
  migration_warnings?: string[]
  model_substitutions?: { purpose: string; saved_model: string; replacement: string }[]
  catalog_version?: number
  preset_update_available?: boolean
  seen_notices?: string[]
  acked_catalog_version?: number
  connections: Connection[]
  analysis: Assignment | null
  vision: Assignment | null
  cover: Assignment | null
  transcription?: { provider: 'whisper_local' | 'sensevoice_local' | 'cloud'; model: string; connection_id?: string; capability?: Capability; model_source?: ModelSource } | null
  cover_enabled: boolean
  /** Explicit "cover follows analysis"; absent only in documents older than the flag. */
  cover_follows_analysis?: boolean | null
  allow_send_frame: boolean
  analysis_mode: 'auto' | 'subtitle' | 'visual'
  allow_visual_screening: boolean
  chunk_size: number
  min_score_threshold: number
  max_clips_per_collection: number
}
export interface ModelEntry { id: string; capability: 'multimodal' | 'text' | null; capability_source?: string; analysis: boolean; image: boolean; asr?: boolean; asr_supported?: boolean; asr_preview?: boolean; asr_note?: string | null; kind?: 'language' | 'image' | 'asr' | 'audio' | 'video' | 'other' }
export interface ModelList { models: ModelEntry[]; source: 'live' | 'cache' | 'catalog'; preview?: boolean; updated_at: number | null; warning?: string }
export interface FetchListResult {
  ok?: boolean
  success?: boolean
  models: string[]
  recommended?: Record<string, string[]>
  truncated?: boolean
  source?: string
  error_type?: string
  hint_key?: string
  message_key?: string
  base_url_host?: string
}
export const modelSettingsApi = {
  get: () => api.get<unknown, ModelSettings>('/settings/ai-models'),
  save: (value: ModelSettings) => api.put<unknown, ModelSettings>('/settings/ai-models', value),
  discover: (connection: Connection, refresh = false) => api.post<unknown, ModelList>('/settings/ai-models/discover', { connection, refresh }),
  test: (connection: Connection, model: string, vision = false, purpose: 'analysis' | 'vision' | 'cover' | 'transcription' = 'analysis') => api.post<unknown, ValidationResult>('/settings/ai-models/test', { connection, model, vision, purpose }),
  fetchList: (connection: Connection) => api.post<unknown, FetchListResult>('/settings/ai-models/fetch-list', { connection }),
}

export function bindingCapability(binding: Assignment | null, lists: Record<string, ModelList>): Capability {
  if (!binding) return 'auto'
  return binding.capability !== 'auto' ? binding.capability : lists[binding.connection_id]?.models.find(m => m.id === binding.model)?.capability || 'auto'
}
