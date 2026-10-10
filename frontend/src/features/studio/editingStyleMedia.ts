import editorialPoster from '../../assets/editing-style/editorial.poster.webp'
import streetPoster from '../../assets/editing-style/street.poster.webp'
import classicPoster from '../../assets/editing-style/classic.poster.webp'
import type { EditingStyle } from './editingStyle'

export const STYLE_POSTERS: Record<EditingStyle, string> = {
  editorial: editorialPoster,
  street: streetPoster,
  classic: classicPoster,
}

type PreviewUrls = { webm: string; mp4: string }

const loaders: Record<EditingStyle, () => Promise<PreviewUrls>> = {
  editorial: async () => ({
    webm: (await import('../../assets/editing-style/editorial.preview.webm?url')).default,
    mp4: (await import('../../assets/editing-style/editorial.preview.mp4?url')).default,
  }),
  street: async () => ({
    webm: (await import('../../assets/editing-style/street.preview.webm?url')).default,
    mp4: (await import('../../assets/editing-style/street.preview.mp4?url')).default,
  }),
  classic: async () => ({
    webm: (await import('../../assets/editing-style/classic.preview.webm?url')).default,
    mp4: (await import('../../assets/editing-style/classic.preview.mp4?url')).default,
  }),
}

const cache = new Map<EditingStyle, Promise<PreviewUrls>>()

/** Fetch one style's silent preview. Callers decide the order. */
export function loadStylePreview(id: EditingStyle): Promise<PreviewUrls> {
  let pending = cache.get(id)
  if (!pending) {
    pending = loaders[id]()
    cache.set(id, pending)
  }
  return pending
}
