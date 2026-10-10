import { buildApiUrl, isApiReady, waitForApiReady } from '../../utils/apiConfig'
import { RECOMMEND_TIMEOUT_MS } from './editingStyle'

/** Ask for a style. The file name is not sent. The caller aborts at 2 seconds. */
export async function requestStyleRecommendation(input: { url?: string; file?: File | null }, signal: AbortSignal): Promise<unknown> {
  if (!isApiReady()) await waitForApiReady(Math.min(1500, RECOMMEND_TIMEOUT_MS))
  if (signal.aborted) throw new DOMException('aborted', 'AbortError')
  const body = new FormData()
  if (input.url) body.append('url', input.url)
  if (input.file) body.append('header', input.file.slice(0, 1024 * 1024), 'clip.mp4')
  const response = await fetch(buildApiUrl('/studio/template-recommend'), { method: 'POST', body, signal })
  if (!response.ok) throw new Error('recommend failed')
  return response.json()
}
