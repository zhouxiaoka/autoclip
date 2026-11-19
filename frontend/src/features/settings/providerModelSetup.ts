import type { Assignment, Connection, ModelEntry, ModelList, ModelSettings } from './modelSettingsApi'
import { isImageModel } from './modelKind'
import { getProvider } from './providerPresets'

/** Only the selected account's discovered models may supply new assignments. */
export function recommendProviderSetup(settings: ModelSettings, connection: Connection, list: ModelList): ModelSettings | null {
  if (list.preview || !['live', 'cache'].includes(list.source)) return null
  const allowed = connection.enabled_model_ids ? new Set(connection.enabled_model_ids) : null
  const models = list.models.filter(model => !allowed || allowed.has(model.id))
  const catalog = getProvider(connection.catalog_provider_id || connection.provider)?.candidates
  const pick = (slot: 'analysis' | 'vision' | 'cover' | 'transcription', eligible: ModelEntry[], preferred: string[] = []) => {
    const current = settings[slot]
    const ids = [current?.connection_id === connection.id ? current.model : '', ...preferred]
    return ids.map(id => eligible.find(model => model.id === id)).find(Boolean) || eligible[0]
  }
  const language = models.filter(m => m.analysis && !isImageModel(m.id) && !m.asr && (!m.kind || m.kind === 'language'))
  const visual = language.filter(m => m.capability === 'multimodal')
  const analysis = pick('analysis', settings.analysis_mode === 'visual' ? visual : language, catalog?.analysis)
  const vision = pick('vision', visual, catalog?.vision)
  const speech = pick('transcription', models.filter(m => m.asr && m.asr_supported && !m.asr_preview), catalog?.asr)
  const cover = pick('cover', models.filter(m => m.image), catalog?.image)
  if (!analysis && (!settings.analysis?.model || settings.analysis.connection_id === connection.id)) return null
  if (!analysis && !vision && !speech && !cover) return null
  const bind = (entry: ModelEntry): Assignment => ({
    connection_id: connection.id, model: entry.id, capability: entry.capability || 'auto', model_source: 'preset',
  })
  const next = { ...settings }
  if (analysis) next.analysis = bind(analysis)
  if (vision) next.vision = bind(vision)
  else if (next.vision?.connection_id === connection.id) next.vision = null
  if (speech) next.transcription = { provider: 'cloud', model: speech.id, connection_id: connection.id, model_source: 'preset' }
  else if (next.transcription?.connection_id === connection.id) next.transcription = { provider: 'whisper_local', model: 'base', model_source: 'preset' }
  if (cover) {
    next.cover = bind(cover)
    next.cover_follows_analysis = !!analysis
  } else if (next.cover?.connection_id === connection.id) {
    next.cover = null
    next.cover_enabled = false
    next.cover_follows_analysis = false
  }
  if (next.cover && next.cover.connection_id !== next.analysis?.connection_id) next.cover_follows_analysis = false
  return next
}
