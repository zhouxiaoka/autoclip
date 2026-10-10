import { buildApiUrl, isApiReady, waitForApiReady } from '../../utils/apiConfig'
import { RECOMMEND_TIMEOUT_MS } from './editingStyle'

function desktopShell(): boolean {
  return typeof window !== 'undefined' && Boolean((window as Window & { __TAURI__?: unknown; __TAURI_INTERNALS__?: unknown }).__TAURI__ || (window as Window & { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__)
}

/** Ask for a style. The file name is not sent. The caller aborts at 2 seconds. */
export async function requestStyleRecommendation(input: { url?: string; file?: File | null }, signal: AbortSignal): Promise<unknown> {
  // The browser dev server already proxies /api. Only the desktop shell has to wait for its port.
  if (desktopShell() && !isApiReady()) await waitForApiReady(Math.min(1500, RECOMMEND_TIMEOUT_MS))
  if (signal.aborted) throw new DOMException('aborted', 'AbortError')
  const body = new FormData()
  if (input.url) body.append('url', input.url)
  if (input.file) body.append('header', input.file.slice(0, 1024 * 1024), 'clip.mp4')
  const response = await fetch(buildApiUrl('/studio/template-recommend'), { method: 'POST', body, signal })
  if (!response.ok) throw new Error('recommend failed')
  return response.json()
}
