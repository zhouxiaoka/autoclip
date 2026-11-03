/**
 * 前端崩溃上报。未配置 VITE_PUBLIC_SENTRY_DSN 或用户关闭时全程 no-op。
 * 不含视频内容、字幕、API key；sendDefaultPii: false。
 */
import * as Sentry from '@sentry/react'

const DSN = import.meta.env.VITE_PUBLIC_SENTRY_DSN
const OPT_OUT_KEY = 'autoclip.crashReports.optOut'
const DAILY_KEY = 'autoclip.sentry.daily'
// Provider answers (401/429/503 and the same closed set the backend drops) stay in PostHog.
const EXPECTED_HTTP = new Set([401, 402, 403, 404, 408, 409, 429, 502, 503, 504])
const EXPECTED_UPSTREAM = new Set([
  'invalid_key', 'insufficient_quota', 'permission_denied', 'model_not_found',
  'bad_endpoint', 'rate_limited', 'upstream_unavailable', 'output_truncated',
])
// Per device, per UTC day: 15 at full fidelity, then 1 in 10, hard stop at 40.
const DAILY_FULL = 15
const DAILY_CAP = 40
const DAILY_SAMPLE_EVERY = 10

let initialized = false
let preferenceOverride: boolean | undefined
let memoryDay = ''
let memorySent = 0
const ANONYMOUS_ID = /^(?:[A-Fa-f0-9]{32}|[A-Fa-f0-9]{8}(?:-[A-Fa-f0-9]{4}){3}-[A-Fa-f0-9]{12})$/
let pendingUserId: string | null = null

function applyAnonymousUser(): void {
  if (!initialized) return
  try {
    if (pendingUserId && isCrashReportsEnabled()) Sentry.setUser({ id: pendingUserId })
    else Sentry.setUser(null)
  } catch { /* identity cannot break crash reporting */ }
}

/** Align Sentry user.id with the PostHog anonymous distinct_id. Id only. */
export function setAnonymousUser(id?: string | null): void {
  pendingUserId = typeof id === 'string' && ANONYMOUS_ID.test(id) ? id : null
  applyAnonymousUser()
}

export function isCrashReportsEnabled(): boolean {
  if (preferenceOverride !== undefined) return preferenceOverride
  try {
    return localStorage.getItem(OPT_OUT_KEY) !== 'true'
  } catch {
    return true
  }
}

/** only the packaged desktop production build reports (not `vite dev`, not a browser tab).*/
function isPackagedDesktop(): boolean {
  return Boolean(import.meta.env.PROD) && Boolean(import.meta.env.VITE_APP_VERSION) &&
    typeof window !== 'undefined' && ('__TAURI_INTERNALS__' in window || '__TAURI__' in window)
}

function providerExpected(tags: { http_status?: unknown, upstream_error_type?: unknown } | undefined): boolean {
  if (!tags) return false
  const status = typeof tags.http_status === 'boolean' ? NaN : Number(tags.http_status)
  if (EXPECTED_HTTP.has(status)) return true
  return EXPECTED_UPSTREAM.has(String(tags.upstream_error_type || ''))
}

function sampledIn(eventId: string | undefined): boolean {
  const hex = String(eventId || '').replace(/-/g, '')
  if (!/^[0-9a-fA-F]+$/.test(hex)) return false
  try {
    return Number(BigInt(`0x${hex}`) % BigInt(DAILY_SAMPLE_EVERY)) === 0
  } catch {
    return false
  }
}

function dailyAllows(eventId: string | undefined): boolean {
  const day = new Date().toISOString().slice(0, 10)
  let stored = 0
  let readable = false
  try {
    const parsed = JSON.parse(localStorage.getItem(DAILY_KEY) || 'null')
    readable = true
    if (parsed && parsed.day === day && Number.isFinite(parsed.sent) && parsed.sent >= 0) {
      stored = Math.floor(parsed.sent)
    }
  } catch { /* blocked storage keeps the in-memory count */ }
  const sent = memoryDay === day ? Math.max(stored, memorySent) : (readable ? stored : 0)
  if (sent >= DAILY_CAP) return false
  if (sent >= DAILY_FULL && !sampledIn(eventId)) return false
  memoryDay = day
  memorySent = sent + 1
  try { localStorage.setItem(DAILY_KEY, JSON.stringify({ day, sent: memorySent })) } catch { /* memory only */ }
  return true
}

export function initSentry(): void {
  if (initialized) return
  if (!DSN) {
    if (import.meta.env.DEV) {
      console.info('[sentry] 未配置 VITE_PUBLIC_SENTRY_DSN，崩溃上报已禁用')
    }
    return
  }
  if (!isPackagedDesktop()) return
  if (!isCrashReportsEnabled()) {
    if (import.meta.env.DEV) {
      console.info('[sentry] 用户已关闭崩溃报告')
    }
    return
  }

  const release = import.meta.env.VITE_APP_VERSION
    ? `autoclip-frontend@${import.meta.env.VITE_APP_VERSION}`
    : undefined

  Sentry.init({
    dsn: DSN,
    release,
    environment: import.meta.env.PROD ? 'production' : 'development',
    sendDefaultPii: false,
    tracesSampleRate: 0,
    integrations: defaults => defaults.filter(integration => integration.name !== "BrowserSession"),
    maxBreadcrumbs: 0,
    beforeSend(event) {
      if (!isCrashReportsEnabled()) return null
      if (providerExpected(event.tags)) return null
      if (!dailyAllows(event.event_id)) return null
      // An allowlist avoids leaking request bodies, console text or exception
      // messages containing subtitles/paths. Preserve debug IDs for source maps.
      const userId = event.user && typeof event.user.id === 'string' ? event.user.id : undefined
      return {
        type: event.type, event_id: event.event_id, timestamp: event.timestamp, platform: event.platform,
        level: event.level, release: event.release, environment: event.environment,
        sdk: event.sdk, debug_meta: event.debug_meta,
        ...(userId && ANONYMOUS_ID.test(userId) ? { user: { id: userId } } : {}),
        tags: { ...(event.tags?.area === 'studio' && (event.tags?.phase === 'native_download' || event.tags?.phase === 'template_picker') ? { area: 'studio', phase: event.tags.phase } : {}), app_locale: typeof document !== "undefined" ? document.documentElement.lang : "unknown" },
        exception: { values: event.exception?.values?.map(value => ({
          type: value.type, value: '[message omitted for privacy]',
          stacktrace: { frames: value.stacktrace?.frames?.map(frame => ({
            filename: frame.filename?.split(/[?#]/)[0], function: frame.function,
            lineno: frame.lineno, colno: frame.colno, in_app: frame.in_app,
          })) },
        })) },
      }
    },
  })
  initialized = true
  applyAnonymousUser()
}

export function setCrashReportsEnabled(enabled: boolean): void {
  preferenceOverride = enabled
  try {
    localStorage.setItem(OPT_OUT_KEY, enabled ? 'false' : 'true')
  } catch {
    /* ignore */
  }
  // beforeSend gates immediately; avoid close()/re-init races on rapid toggles.
  applyAnonymousUser()
  if (!enabled) return
  if (!initialized) initSentry()
}

export function captureException(error: unknown): void {
  if (!initialized || !isCrashReportsEnabled()) return
  Sentry.captureException(error)
}

/** Native disk failures have no backend exception; report them once here. */
export function captureStudioException(error: unknown, phase: 'native_download' | 'template_picker'): void {
  if (!initialized || !isCrashReportsEnabled()) return
  try {
    Sentry.withScope(scope => {
      scope.setTag('area', 'studio')
      scope.setTag('phase', phase)
      Sentry.captureException(error)
    })
  } catch { /* monitoring must not break the download recovery UI */ }
}
