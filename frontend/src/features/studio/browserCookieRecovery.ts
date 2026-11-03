/** #481: a blocked or bot-checked link, and a locked browser, both return to the import picker. */

export const BROWSER_COOKIE_FOCUS = 'browser-cookies'
export const BROWSER_COOKIE_IMPORT_PATH = `/?focus=${BROWSER_COOKIE_FOCUS}`
/** Keep in sync with download_recovery.COOKIE_ACCESS_HINT and the eight locale catalogs. */
export const COOKIE_ACCESS_HINT = '无法读取浏览器登录信息。请完全退出该浏览器后再重试，或换一个已登录的浏览器。公开视频也可以不选浏览器。原素材已保留。'

const RECOVERY_URL_KEY = 'autoclip.browserCookieRecoveryUrl'
const HTTP_URL = /^https?:\/\/\S+$/i

export function browserCookieRecovery(code?: string | null, error?: string | null): boolean {
  return code === 'source_blocked' || (!!error && error === COOKIE_ACCESS_HINT)
}

function remember(url: string) {
  try {
    if (typeof sessionStorage === 'undefined') return
    if (url) sessionStorage.setItem(RECOVERY_URL_KEY, url)
    else sessionStorage.removeItem(RECOVERY_URL_KEY)
  } catch { /* private mode, or a test sandbox without storage */ }
}

/** Home import, with the browser picker expanded. A link is staged only when it is a plain http(s) URL. */
export function stageBrowserCookieRecovery(sourceUrl?: string | null): string {
  const url = typeof sourceUrl === 'string' && sourceUrl.length <= 2000 && HTTP_URL.test(sourceUrl) ? sourceUrl : ''
  remember(url)
  return BROWSER_COOKIE_IMPORT_PATH
}

export function cookieAssistFromLocation(search: string): boolean {
  // Hand-parsed so a vm test sandbox does not need URLSearchParams.
  const query = (search.startsWith('?') ? search.slice(1) : search).split('#')[0]
  if (!query) return false
  try {
    for (const part of query.split('&')) {
      if (!part) continue
      const eq = part.indexOf('=')
      const key = decodeURIComponent(eq < 0 ? part : part.slice(0, eq))
      const value = decodeURIComponent((eq < 0 ? '' : part.slice(eq + 1)).replace(/\+/g, ' '))
      if (key === 'focus' && value === BROWSER_COOKIE_FOCUS) return true
    }
  } catch {
    return false
  }
  return false
}

export function stagedRecoveryUrl(): string {
  try {
    if (typeof sessionStorage === 'undefined') return ''
    const url = sessionStorage.getItem(RECOVERY_URL_KEY) || ''
    return url.length <= 2000 && HTTP_URL.test(url) ? url : ''
  } catch {
    return ''
  }
}
