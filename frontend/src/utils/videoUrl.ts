/** Classify supported video links using their host, path and query independently. */
export function getVideoType(value: string): 'bilibili' | 'youtube' | null {
  let url: URL
  try { url = new URL(value.trim()) } catch { return null }
  if (!['http:', 'https:'].includes(url.protocol)) return null
  const host = url.hostname.toLowerCase()
  const path = url.pathname
  if (['bilibili.com', 'www.bilibili.com'].includes(host) &&
      /^\/video\/(?:BV[0-9a-z]+|av\d+)\/?$/i.test(path)) return 'bilibili'
  if (host === 'b23.tv' && /^\/[0-9a-z]+\/?$/i.test(path)) return 'bilibili'
  if (host === 'youtu.be' && /^\/[a-zA-Z0-9_-]+\/?$/.test(path)) return 'youtube'
  if (['youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'].includes(host)) {
    if (path === '/watch' && /^[a-zA-Z0-9_-]+$/.test(url.searchParams.get('v') || '')) return 'youtube'
    if (/^\/(?:shorts|live|embed|v)\/[a-zA-Z0-9_-]+\/?$/.test(path)) return 'youtube'
  }
  return null
}

export const validateVideoUrl = (value: string): boolean => getVideoType(value) !== null
