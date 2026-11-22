/**
 * Image-model id markers — must stay identical to backend.core.model_catalog._IMAGE_MARKERS.
 * Used when ModelEntry.image / analysis flags are missing (backfill / custom input).
 */

export const IMAGE_MARKERS = [
  'gpt-image',
  'dall-e',
  'seedream',
  'wanx',
  'flux',
  'imagen',
  't2i',
  'midjourney',
  'ideogram',
  'recraft',
  'stable-diffusion',
  'sdxl',
  'sd3',
  'kolors',
  'cogview',
  'hunyuan-image',
  'qwen-image',
] as const

/** Substring match on the lowercased model id (same rule as backend is_image_model). */
export function isImageMarker(id: string | null | undefined): boolean {
  const name = (id || '').toLowerCase()
  if (!name) return false
  return IMAGE_MARKERS.some(marker => name.includes(marker))
}

/**
 * Prefer ModelEntry flags when present; fall back to id markers.
 * Priority: entry.image && !entry.analysis → image; else marker match.
 */
export function isImageModel(
  id: string | null | undefined,
  entry?: { image?: boolean; analysis?: boolean } | null,
): boolean {
  if (entry && entry.image === true && entry.analysis !== true) return true
  return isImageMarker(id)
}
