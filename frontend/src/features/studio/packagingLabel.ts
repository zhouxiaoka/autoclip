import { t } from '../../i18n'
import type { Packaging } from './types'

/** Template name shown on result cards and in the editor. */
export function packagingLabel(packaging: Packaging): string {
  if (packaging.template === 'podcast_en') return t('播客式')
  const bilingual = (!packaging.translation_status || packaging.translation_status === 'complete') && packaging.captions_enabled !== false && packaging.source_language === 'en' && !packaging.burned_captions && packaging.cues.some(cue => cue.original.trim() && /[㐀-鿿]/.test(cue.text))
  return bilingual ? t('访谈式 · 中英字幕') : t('访谈式')
}

/** Describe actual retained captions, including old drafts with an empty fallback. */
export function packagingFallbackHint(packaging: Packaging, warnings: string[] = [], subtitlesRequested = true): string {
  if (!subtitlesRequested || packaging.captions_enabled === false) return ''
  if (packaging.translation_status === 'partial' || packaging.translation_status === 'source_fallback') return t('字幕翻译尚未完成，请检查后再发布')
  if (!packaging.fallback) return ''
  if (packaging.translation_status === 'complete') return t('字幕翻译已完成，使用简化包装')
  const hasCaptions = packaging.cues.length > 0 || packaging.burned_captions || warnings.includes('包装未能完整生成，已使用原字幕')
  // Captions switched off (or caption-free visual highlights): never claim captions were kept.
  return hasCaptions ? t('包装未能完整生成，已保留可用字幕') : t('包装未能完整生成，字幕暂不可用')
}
