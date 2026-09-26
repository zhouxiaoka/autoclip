import { apiConfigManager } from './apiConfig'

export const isDesktop = () => typeof window !== 'undefined' &&
  Boolean((window as any).__TAURI__ || (window as any).__TAURI_INTERNALS__)

export async function backendUrl(path: string): Promise<string> {
  if (isDesktop() && !await apiConfigManager.waitForReady()) throw new Error('Backend is not ready')
  const base = apiConfigManager.getBaseUrl()
  if (path.startsWith('/') && !path.startsWith('//') && isDesktop()) {
    return new URL(path, base).href
  }
  return path
}

export function authHeaders(url: string): Record<string, string> {
  const base = new URL(apiConfigManager.getBaseUrl(), window.location.href)
  const target = new URL(url, window.location.href)
  const token = apiConfigManager.getAuthToken()
  // Never forward the installation capability to external URLs.
  return token && target.origin === base.origin && target.pathname.startsWith('/api/')
    ? { Authorization: `Bearer ${token}` } : {}
}

export async function authenticatedFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const url = await backendUrl(path)
  const headers = new Headers(options.headers)
  Object.entries(authHeaders(url)).forEach(([name, value]) => headers.set(name, value))
  const response = await fetch(url, { ...options, headers, credentials: 'same-origin', redirect: 'error' })
  if (response.status === 401 && !url.endsWith('/api/auth/login')) window.dispatchEvent(new Event('autoclip-auth-required'))
  return response
}

export async function authorizeMediaUrl(path: string): Promise<string> {
  const url = await backendUrl(path)
  if (!isDesktop()) return url
  const target = new URL(url, window.location.href)
  const base = new URL(apiConfigManager.getBaseUrl(), window.location.href)
  if (target.origin !== base.origin || !target.pathname.startsWith('/api/v1/')) throw new Error('Invalid media URL')
  const response = await authenticatedFetch('/api/auth/media', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: target.pathname + target.search }),
  })
  if (!response.ok) throw new Error('Media authorization failed')
  const { token } = await response.json()
  target.searchParams.set('_media', token)
  return target.href
}
