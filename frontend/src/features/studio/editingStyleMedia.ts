import editorialPoster from '../../assets/editing-style/editorial.poster.webp'
import streetPoster from '../../assets/editing-style/street.poster.webp'
import newsPoster from '../../assets/editing-style/news.poster.webp'
import cinemaPoster from '../../assets/editing-style/cinema.poster.webp'
import classicPoster from '../../assets/editing-style/classic.poster.webp'
import type { BuiltinTemplateChoice, EditingStyle } from './editingStyle'
import { resolveTemplateAssetUrl, type TemplateCatalogItem } from './templateCatalogClient'

export const STYLE_POSTERS: Record<BuiltinTemplateChoice, string> = {
  editorial: editorialPoster,
  street: streetPoster,
  news: newsPoster,
  cinema: cinemaPoster,
  classic: classicPoster,
}

type PreviewUrls = { webm: string; mp4: string }

const loaders: Record<BuiltinTemplateChoice, () => Promise<PreviewUrls>> = {
  editorial: async () => ({
    webm: (await import('../../assets/editing-style/editorial.preview.webm?url')).default,
    mp4: (await import('../../assets/editing-style/editorial.preview.mp4?url')).default,
  }),
  street: async () => ({
    webm: (await import('../../assets/editing-style/street.preview.webm?url')).default,
    mp4: (await import('../../assets/editing-style/street.preview.mp4?url')).default,
  }),
  news: async () => ({
    webm: (await import('../../assets/editing-style/news.preview.webm?url')).default,
    mp4: (await import('../../assets/editing-style/news.preview.mp4?url')).default,
  }),
  cinema: async () => ({
    webm: (await import('../../assets/editing-style/cinema.preview.webm?url')).default,
    mp4: (await import('../../assets/editing-style/cinema.preview.mp4?url')).default,
  }),
  classic: async () => ({
    webm: (await import('../../assets/editing-style/classic.preview.webm?url')).default,
    mp4: (await import('../../assets/editing-style/classic.preview.mp4?url')).default,
  }),
}

const cache = new Map<string, Promise<PreviewUrls>>()

export function posterForTemplate(id: EditingStyle, item?: TemplateCatalogItem): string {
  const remoteOrLocal = resolveTemplateAssetUrl(item?.poster_url)
  if (remoteOrLocal) return remoteOrLocal
  return STYLE_POSTERS[id as BuiltinTemplateChoice] || classicPoster
}

/** Fetch one style's silent preview. Supports built-in bundled assets and dynamic template URLs. */
export function loadStylePreview(id: EditingStyle, item?: TemplateCatalogItem): Promise<PreviewUrls> {
  const dynamicMp4 = resolveTemplateAssetUrl(item?.preview_mp4_url)
  const dynamicWebm = resolveTemplateAssetUrl(item?.preview_webm_url)
  if (dynamicMp4 || dynamicWebm) {
    return Promise.resolve({
      webm: dynamicWebm || dynamicMp4 || '',
      mp4: dynamicMp4 || dynamicWebm || '',
    })
  }
  const loader = loaders[id as BuiltinTemplateChoice]
  if (!loader) {
    return Promise.resolve({ webm: '', mp4: '' })
  }
  let pending = cache.get(id)
  if (!pending) {
    pending = loader().catch(() => ({ webm: '', mp4: '' }))
    cache.set(id, pending)
  }
  return pending
}
