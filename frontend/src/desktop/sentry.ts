/**
 * 前端崩溃上报。未配置 VITE_PUBLIC_SENTRY_DSN 或用户关闭时全程 no-op。
 * 不含视频内容、字幕、API key；sendDefaultPii: false。
 */
import * as Sentry from '@sentry/react'

const DSN = import.meta.env.VITE_PUBLIC_SENTRY_DSN
const OPT_OUT_KEY = 'autoclip.crashReports.optOut'

let initialized = false
let preferenceOverride: boolean | undefined

export function isCrashReportsEnabled(): boolean {
  if (preferenceOverride !== undefined) return preferenceOverride
  try {
    return localStorage.getItem(OPT_OUT_KEY) !== 'true'
  } catch {
    return true
  }
}

export function initSentry(): void {
  if (initialized) return
  if (!DSN) {
    if (import.meta.env.DEV) {
      console.info('[sentry] 未配置 VITE_PUBLIC_SENTRY_DSN，崩溃上报已禁用')
    }
    return
  }
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
      // An allowlist avoids leaking request bodies, console text or exception
      // messages containing subtitles/paths. Preserve debug IDs for source maps.
      return {
        type: event.type, event_id: event.event_id, timestamp: event.timestamp, platform: event.platform,
        level: event.level, release: event.release, environment: event.environment,
        sdk: event.sdk, debug_meta: event.debug_meta,
        tags: { app_locale: typeof document !== "undefined" ? document.documentElement.lang : "unknown" },
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
}

export function setCrashReportsEnabled(enabled: boolean): void {
  preferenceOverride = enabled
  try {
    localStorage.setItem(OPT_OUT_KEY, enabled ? 'false' : 'true')
  } catch {
    /* ignore */
  }
  // beforeSend gates immediately; avoid close()/re-init races on rapid toggles.
  if (!enabled) return
  if (!initialized) initSentry()
}

export function captureException(error: unknown): void {
  if (!initialized || !isCrashReportsEnabled()) return
  Sentry.captureException(error)
}
