import { t } from '../../i18n'
import type { Packaging } from './types'

/** Template name shown on result cards and in the editor. */
export function packagingLabel(packaging: Packaging): string {
  if (packaging.template === 'podcast_en') return t('播客式')
  return packaging.source_language !== 'zh' && !packaging.burned_captions ? t('访谈式 · 中英字幕') : t('访谈式')
}
