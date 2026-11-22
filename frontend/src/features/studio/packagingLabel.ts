import { t } from '../../i18n'
import type { Packaging } from './types'

/** Template name shown on result cards and in the editor. */
export function packagingLabel(packaging: Packaging): string {
  if (packaging.template === 'podcast_en') return t('播客式')
  const bilingual = packaging.captions_enabled !== false && packaging.source_language === 'en' && !packaging.burned_captions && packaging.cues.some(cue => cue.original.trim() && /[㐀-鿿]/.test(cue.text))
  return bilingual ? t('访谈式 · 中英字幕') : t('访谈式')
}

/** Describe actual retained captions, including old drafts with an empty fallback. */
export function packagingFallbackHint(packaging: Packaging, warnings: string[] = [], subtitlesRequested = true): string {
  if (!packaging.fallback) return ''
  const hasCaptions = packaging.cues.length > 0 || packaging.burned_captions || warnings.includes('包装未能完整生成，已使用原字幕')
  // Captions switched off (or caption-free visual highlights): never claim captions were kept.
  if (!subtitlesRequested) return ''
  if (packaging.cues.length && packaging.fallback_captions === 'source') return t('包装样式未完整生成，已保留原文字幕，缺少译文')
  if (packaging.cues.length && packaging.fallback_captions === 'translated') return t('包装样式未完整生成，已保留翻译字幕')
  return hasCaptions ? t('包装未能完整生成，已保留可用字幕') : t('包装未能完整生成，字幕暂不可用')
}
