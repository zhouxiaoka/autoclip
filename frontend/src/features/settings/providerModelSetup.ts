import type { Assignment, Connection, ModelEntry, ModelList, ModelSettings } from './modelSettingsApi'
import { isImageModel } from './modelKind'
import { getProvider } from './providerPresets'

/** Prefer preset curated analysis candidates over arbitrary raw `/models` ordering when probing. */
export function pickRecommendedTestModel(connection: Pick<Connection, 'provider' | 'catalog_provider_id' | 'enabled_model_ids' | 'failed_model_checks'>, list?: ModelList | null): string {
  const catalog = getProvider(connection.catalog_provider_id || connection.provider)?.candidates
  const preferred = catalog?.analysis || []
  const allowed = connection.enabled_model_ids ? new Set(connection.enabled_model_ids) : null
  const eligible = (list?.models || []).filter(m =>
    (!allowed || allowed.has(m.id))
    && m.analysis
    && !isImageModel(m.id)
    && !m.asr
    && (!m.kind || m.kind === 'language')
    && !connection.failed_model_checks?.some(f => f.purpose === 'analysis' && f.model === m.id),
  )
  for (const id of preferred) {
    const hit = eligible.find(m => m.id === id)
    if (hit) return hit.id
  }
  return eligible[0]?.id || preferred[0] || ''
}

/** Only the selected account's discovered models may supply new assignments. */
export function recommendProviderSetup(settings: ModelSettings, connection: Connection, list: ModelList): ModelSettings | null {
  if (list.preview || !['live', 'cache'].includes(list.source)) return null
  const allowed = connection.enabled_model_ids ? new Set(connection.enabled_model_ids) : null
  const models = list.models.filter(model => !allowed || allowed.has(model.id))
  const catalog = getProvider(connection.catalog_provider_id || connection.provider)?.candidates
  const pick = (slot: 'analysis' | 'vision' | 'cover' | 'transcription', eligible: ModelEntry[], preferred: string[] = []) => {
    eligible = eligible.filter(m => !connection.failed_model_checks?.some(f => f.purpose === slot && f.model === m.id))
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
    next.cover_enabled = !settings.prefer_local_cover
    next.cover = bind(cover)
    next.cover_follows_analysis = !!analysis
  } else if (next.cover?.connection_id === connection.id || (analysis && settings.cover_follows_analysis)) {
    next.cover = null
    next.cover_enabled = false
    next.cover_follows_analysis = false
  }
  return preserveFixedAssignments(settings, next)
}

export function preserveFixedAssignments(settings: ModelSettings, proposed: ModelSettings): ModelSettings {
  const next = { ...proposed }
  for (const role of ['analysis', 'vision', 'cover'] as const) {
    const binding = settings[role]
    if (binding?.model && binding.model_source !== 'preset') next[role] = binding
  }
  const speech = settings.transcription
  if (speech?.model && speech.model_source !== 'preset') next.transcription = speech
  if (settings.cover?.model && settings.cover.model_source !== 'preset') {
    next.cover_enabled = settings.cover_enabled
    next.cover_follows_analysis = settings.cover_follows_analysis
  }
  if (next.cover && next.cover.connection_id !== next.analysis?.connection_id) next.cover_follows_analysis = false
  return next
}
