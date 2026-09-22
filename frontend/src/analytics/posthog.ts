/**
 * PostHog 产品分析 / 埋点
 *
 * 设计目标（见 ROADMAP.md Phase 0）：匿名、可关、本地缓冲。
 * - 匿名：默认不采集任何 PII，未登录前用匿名设备 ID；person profiles 仅在 identify 后创建。
 * - 可关：用户可在设置里关闭（opt-out），状态持久化在 localStorage，应用重启后仍生效。
 * - 本地缓冲：posthog-js 默认在内存中批量缓冲事件，断网/退出代理时不丢主流程。
 *
 * 没有配置 VITE_PUBLIC_POSTHOG_KEY 时，本模块全部为 no-op，
 * 因此 dev 环境（无 key）不会污染线上数据。
 */
import posthog from 'posthog-js'
import { routeName, type Properties } from './workflow'

export const POSTHOG_KEY = import.meta.env.VITE_PUBLIC_POSTHOG_KEY as string | undefined
export const POSTHOG_HOST =
  (import.meta.env.VITE_PUBLIC_POSTHOG_HOST as string | undefined) ??
  'https://us.i.posthog.com'

/** 用户埋点开关偏好的存储键（true = 已关闭采集）。 */
const OPT_OUT_STORAGE_KEY = 'autoclip.analytics.optOut'

let initialized = false
let preferenceOverride: boolean | undefined
const preferenceListeners = new Set<() => void>()
export function onAnalyticsPreferenceChange(listener: () => void): () => void {
  preferenceListeners.add(listener)
  return () => { preferenceListeners.delete(listener) }
}

/** Never let analytics failures change a successful product operation. */
export function captureBusinessEvent(name: string, properties: Properties = {}): boolean {
  if (!initialized || !isAnalyticsEnabled()) return false
  try {
    return posthog.capture(name, {
      schema_version: 2,
      analytics_environment: import.meta.env.DEV ? 'development' : 'production',
      runtime: '__TAURI_INTERNALS__' in window ? 'desktop' : 'web',
      entrypoint: 'ui',
      app_locale: typeof document !== 'undefined' ? document.documentElement.lang : 'unknown',
      system_locale: typeof navigator !== 'undefined' ? navigator.language : 'unknown',
      ...properties,
    }) !== undefined
  } catch { return false }
}

/** 是否启用了埋点（已配置 key 且用户未关闭）。 */
export function isAnalyticsEnabled(): boolean {
  if (!POSTHOG_KEY) return false
  try {
    return localStorage.getItem(OPT_OUT_STORAGE_KEY) !== 'true'
  } catch {
    return preferenceOverride ?? true
  }
}

/**
 * 初始化 PostHog。应在应用启动时调用一次。
 * 无 key 时直接返回，不做任何网络请求。
 */
export function initAnalytics(): void {
  if (initialized) return
  if (!POSTHOG_KEY) {
    if (import.meta.env.DEV) {
      console.info('[analytics] 未配置 VITE_PUBLIC_POSTHOG_KEY，埋点已禁用')
    }
    return
  }

  try {
    posthog.init(POSTHOG_KEY, {
    api_host: POSTHOG_HOST,
    // 桌面端从 file:// / 自定义协议加载，cookie 不可靠，统一用 localStorage 持久化匿名 ID
    persistence: 'localStorage',
    // 未登录前不创建 person profile，保持匿名；登录后通过 identify 关联（见 ROADMAP Phase 1）
    person_profiles: 'identified_only',
    // Business events are explicit; DOM text may contain filenames or subtitles.
    autocapture: false,
    capture_performance: false,
    // 隐私优先：默认不录屏（PostHog 端也需另行开启）
    disable_session_recording: true,
    // HashRouter 下手动上报 pageview（见 trackPageview）
    capture_pageview: false,
    capture_pageleave: false,
    property_denylist: ['$current_url', '$referrer', '$initial_current_url', '$initial_referrer'],
    // 尊重用户在本机的关闭偏好
    opt_out_capturing_by_default: !isAnalyticsEnabled(),
    loaded: (ph) => {
      if (import.meta.env.DEV) ph.debug()
    },
    })
    initialized = true
  } catch {
    initialized = false
  }
}

/**
 * 打开/关闭埋点采集（用于设置页开关）。会持久化到 localStorage。
 */
export function setAnalyticsEnabled(enabled: boolean): void {
  preferenceOverride = enabled
  try {
    localStorage.setItem(OPT_OUT_STORAGE_KEY, enabled ? 'false' : 'true')
  } catch {
    /* localStorage 不可用时忽略 */
  }
  for (const listener of preferenceListeners) listener()
  if (!initialized) return
  try {
    if (enabled) posthog.opt_in_capturing()
    else posthog.opt_out_capturing()
  } catch { /* analytics cannot break settings */ }
}

/** 上报一次 pageview（在路由变化时调用）。 */
export function trackPageview(path: string): void {
  captureBusinessEvent('$pageview', { route: routeName(path) })
}

/** 登录后关联身份（Phase 1 接入账号时使用）。 */
export function identifyUser(
  distinctId: string,
  properties?: Record<string, unknown>,
): void {
  if (!initialized) return
  posthog.identify(distinctId, properties)
}

/** 登出时重置匿名身份。 */
export function resetUser(): void {
  if (!initialized) return
  posthog.reset()
}

export { posthog }
