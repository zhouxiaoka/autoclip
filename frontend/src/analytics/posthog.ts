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
import { apiConfigManager } from '../utils/apiConfig'
import { routeName, type Properties } from './workflow'
import { nativeRuntime, runtimeProperties } from './runtime'

export const POSTHOG_KEY = import.meta.env.VITE_PUBLIC_POSTHOG_KEY as string | undefined
export const POSTHOG_HOST =
  (import.meta.env.VITE_PUBLIC_POSTHOG_HOST as string | undefined) ??
  'https://us.i.posthog.com'

/** 用户埋点开关偏好的存储键（true = 已关闭采集）。 */
const OPT_OUT_STORAGE_KEY = 'autoclip.analytics.optOut'

let initialized = false
let flagsNetworkEnabled = false
let preferenceOverride: boolean | undefined
let publishedDistinctId = ''
let pendingDistinctId = ''
let retryIdentity = false
let watchingIdentity = false
let identityRetryTimer: ReturnType<typeof setTimeout> | undefined
let identityRetries = 0
let publishedConsent: boolean | undefined
let inflightConsent: boolean | undefined
let backendDistinctId = ''
let privacyResolved = false
let privacyInflight = false
let watchingConsent = false
const preferenceListeners = new Set<() => void>()
let consentRetries = 0
let consentRetryTimer: ReturnType<typeof setTimeout> | undefined
const ANONYMOUS_ID = /^(?:[A-Fa-f0-9]{32}|[A-Fa-f0-9]{8}(?:-[A-Fa-f0-9]{4}){3}-[A-Fa-f0-9]{12})$/

/** Persist the SDK's anonymous id so backend events join the same person and experiment. */
function publishAnonymousId(): void {
  if (!initialized || !isAnalyticsEnabled() || typeof fetch !== 'function') return
  let id = ''
  try { id = String(posthog.get_distinct_id?.() || '') } catch { return }
  if (!ANONYMOUS_ID.test(id) || id === publishedDistinctId) return
  // The SDK id is frozen at launch. A newer id already in analytics.json must win.
  if (privacyInflight) return
  const launchId = nativeRuntime().distinct_id
  if (backendDistinctId && id === launchId && id !== backendDistinctId) return
  syncSentryUser(id)
  // Packaged webviews cannot PUT to the initial relative /api/v1 URL.
  if (typeof window !== 'undefined' && ('__TAURI_INTERNALS__' in window || '__TAURI__' in window)
      && !apiConfigManager.isReady()) return
  // The desktop API port often arrives while the first attempt is still in flight.
  if (pendingDistinctId) {
    retryIdentity = true
    return
  }
  pendingDistinctId = id
  retryIdentity = false
  const controller = typeof AbortController === 'function' ? new AbortController() : undefined
  const timeout = controller ? setTimeout(() => controller.abort(), 5000) : undefined
  const finish = (ok: boolean) => {
    if (timeout !== undefined) clearTimeout(timeout)
    if (pendingDistinctId === id) pendingDistinctId = ''
    if (ok && isAnalyticsEnabled()) {
      publishedDistinctId = id
      backendDistinctId = id
      identityRetries = 0
      if (retryIdentity) {
        retryIdentity = false
        publishAnonymousId()
      }
    } else if (retryIdentity && isAnalyticsEnabled()) {
      retryIdentity = false
      publishAnonymousId()
    } else if (isAnalyticsEnabled() && identityRetries < 5 && typeof setTimeout === 'function') {
      // A ready port can still race a restart or a failed first request.
      if (identityRetryTimer !== undefined) clearTimeout(identityRetryTimer)
      identityRetryTimer = setTimeout(() => {
        identityRetryTimer = undefined
        publishAnonymousId()
      }, 1000 * 2 ** identityRetries++)
    }
  }
  try {
    const base = String(apiConfigManager.getBaseUrl() || '/api/v1').replace(/\/$/, '')
    void fetch(`${base}/settings/analytics-identity`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ distinct_id: id }),
      ...(controller ? { signal: controller.signal } : {}),
    }).then((response) => finish(Boolean(response?.ok))).catch(() => finish(false))
  } catch {
    finish(false)
  }
}

/**
 * Tell the backend about an opt-out so backend Sentry (API and worker processes) stops
 * attaching the anonymous user.id. Once the backend is ready the persisted preference is
 * synced (on or off), so a re-enable whose write failed cannot leave UI=on / backend=off.
 *
 * X2r: mark published only after a successful PUT; retry failures; serialize so a rapid
 * toggle cannot leave UI=off / backend=on (one in-flight request, then sync to latest).
 */
/**
 * the preference the backend should hold. If the saved preference cannot be
 * read (localStorage throws) and the user has not chosen in this session, only "off"
 * may be sent — never "on".
 */
/** No saved choice yet. An explicit on/off, or storage that cannot be read, is not implicit. */
function implicitAnalyticsDefault(): boolean {
  if (preferenceOverride !== undefined) return false
  try {
    return localStorage.getItem(OPT_OUT_STORAGE_KEY) === null
  } catch {
    return false
  }
}

function stopCapturing(): void {
  const optOut = posthog.opt_out_capturing as (options?: { captureEventName?: string | null }) => void
  try {
    optOut({ captureEventName: null })
  } catch {
    try { posthog.opt_out_capturing() } catch { /* analytics cannot break settings */ }
  }
  disableFlagNetwork()
  publishedDistinctId = ''
  if (identityRetryTimer !== undefined) clearTimeout(identityRetryTimer)
  identityRetryTimer = undefined
  identityRetries = 0
  if (consentRetryTimer !== undefined) clearTimeout(consentRetryTimer)
  consentRetryTimer = undefined
  consentRetries = 0
  syncSentryUser(null)
}

function adoptBackendOptOut(): void {
  preferenceOverride = false
  try { localStorage.setItem(OPT_OUT_STORAGE_KEY, 'true') } catch { /* this session still stays off */ }
  for (const listener of preferenceListeners) { try { listener() } catch { /* isolate observers */ } }
  if (initialized) stopCapturing()
}

function consentIntent(): boolean {
  if (!POSTHOG_KEY) return false
  // re-read the shared storage on every send/retry. Another window may have turned
  // analytics off since this one queued an "on"; storage OFF always wins over a stale intent.
  // an explicit session OFF wins even when the storage write failed and storage
  // still reads the old "on" — otherwise "off" would never be sent.
  if (preferenceOverride === false) return false
  try {
    // Shared storage OFF still vetoes a stale session/queued "on".
    return localStorage.getItem(OPT_OUT_STORAGE_KEY) !== 'true'
  } catch {
    return false
  }
}

function publishConsent(): void {
  const enabled = consentIntent()
  if (typeof fetch !== 'function') return
  if (!watchingConsent) {
    watchingConsent = true
    try { apiConfigManager.addListener(() => publishConsent()) } catch { /* port can arrive later */ }
  }
  if (typeof window !== 'undefined' && ('__TAURI_INTERNALS__' in window || '__TAURI__' in window)
      && !apiConfigManager.isReady()) return
  // An implicit "on" must not overwrite a backend opt-out. Ask once, then PUT the result.
  // A fetch that throws in the same turn (tests, unreachable host) must not swallow the
  // identity PUT that init issues before the next microtask.
  if (implicitAnalyticsDefault() && !privacyResolved && !privacyInflight) {
    privacyInflight = true
    const release = (waited: boolean) => {
      privacyInflight = false
      privacyResolved = true
      if (waited) {
        publishConsent()
        publishAnonymousId()
      }
    }
    try {
      const base = String(apiConfigManager.getBaseUrl() || '/api/v1').replace(/\/$/, '')
      const pending = fetch(`${base}/settings/privacy`, { method: 'GET' })
      if (pending && typeof (pending as Promise<Response>).then === 'function') {
        void (pending as Promise<Response>).then(async (response) => {
          if (!response?.ok || typeof response.json !== 'function') return
          const body = await response.json()
          if (body && typeof body.distinct_id === 'string' && ANONYMOUS_ID.test(body.distinct_id)) {
            backendDistinctId = body.distinct_id
          }
          if (body && body.analytics === false && implicitAnalyticsDefault()) adoptBackendOptOut()
        }).catch(() => undefined).then(() => release(true))
        return
      }
    } catch { /* unknown backend keeps today's consent PUT */ }
    release(false)
  }
  // Already in sync and nothing in flight. publishedConsent === undefined means the
  // backend state is unknown (fresh launch, or a PUT whose response was lost), so the
  // latest preference is always sent — including "on" (startup sync, lost response).
  if (inflightConsent === undefined && publishedConsent === enabled) return
  // One in-flight PUT at a time; finish() re-enters with the latest UI value.
  if (inflightConsent !== undefined) return

  inflightConsent = enabled
  const controller = typeof AbortController === 'function' ? new AbortController() : undefined
  const timeout = controller ? setTimeout(() => controller.abort(), 5000) : undefined
  const finish = (ok: boolean) => {
    if (timeout !== undefined) clearTimeout(timeout)
    const sent = inflightConsent
    inflightConsent = undefined
    if (ok) {
      publishedConsent = sent
      consentRetries = 0
      // UI may have moved while the PUT was in flight — sync to the latest preference.
      if (publishedConsent !== consentIntent()) publishConsent()
      return
    }
    // The backend may or may not have applied the PUT (e.g. written but response lost):
    // forget what we think it holds so the next intent is never skipped as "in sync".
    publishedConsent = undefined
    if (consentRetries < 5 && typeof setTimeout === 'function') {
      // Retry against whatever the UI wants now (not a stale mid-toggle value).
      if (consentRetryTimer !== undefined) clearTimeout(consentRetryTimer)
      consentRetryTimer = setTimeout(() => {
        consentRetryTimer = undefined
        publishConsent()
      }, 1000 * 2 ** consentRetries++)
      return
    }
    if (!consentIntent() && typeof setTimeout === 'function') {
      // an opt-out never gives up. Keep retrying (capped) until the API recovers.
      if (consentRetryTimer !== undefined) clearTimeout(consentRetryTimer)
      consentRetryTimer = setTimeout(() => {
        consentRetryTimer = undefined
        publishConsent()
      }, 30000)
      return
    }
    consentRetries = 0
    // Exhausted for "on"; a later toggle or apiConfig listener will try again.
  }
  try {
    const base = String(apiConfigManager.getBaseUrl() || '/api/v1').replace(/\/$/, '')
    void fetch(`${base}/settings/analytics-consent`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
      ...(controller ? { signal: controller.signal } : {}),
    }).then((response) => finish(Boolean(response?.ok))).catch(() => finish(false))
  } catch {
    finish(false)
  }
}

function syncSentryUser(id: string | null): void {
  try {
    void import('../desktop/sentry').then((mod) => {
      try { mod.setAnonymousUser(id) } catch { /* identity cannot break analytics */ }
    }).catch(() => undefined)
  } catch { /* analytics.test.cjs require() must not throw */ }
}

function watchAnonymousId(): void {
  if (watchingIdentity) return
  watchingIdentity = true
  try { apiConfigManager.addListener(() => {
    identityRetries = 0
    publishAnonymousId()
  }) } catch { /* backend port can arrive later */ }
}

const remoteFlagListeners = new Set<() => void>()
export function onAnalyticsPreferenceChange(listener: () => void): () => void {
  preferenceListeners.add(listener)
  return () => { preferenceListeners.delete(listener) }
}
export function subscribeRemoteFlags(listener: () => void): () => void {
  remoteFlagListeners.add(listener)
  return () => { remoteFlagListeners.delete(listener) }
}
// W157-N3: posthog-js restores the previous session's flags from its own persistence
// before the network answers. After an upgrade those are the old version's values
// (e.g. pkg_templates_v1=false from the 1.5.6 cohort), so ignore them until this
// session's flag response arrives.
let remoteFlagsFresh = false
export function markRemoteFlagsResponse(errorsLoading?: boolean): void {
  if (!errorsLoading) remoteFlagsFresh = true
  notifyRemoteFlags()
}
function notifyRemoteFlags() {
  for (const listener of remoteFlagListeners) {
    try { listener() } catch { /* flag subscribers cannot break analytics */ }
  }
}

/**
 * Already-loaded flag value. Never calls the network.
 * Returns undefined unless analytics is on and flag requests were enabled at init.
 */
export function readLoadedFlag(name: string): unknown {
  if (!initialized || !flagsNetworkEnabled || !isAnalyticsEnabled() || !remoteFlagsFresh) return undefined
  try {
    const variants = posthog.featureFlags?.getFlagVariants?.()
    if (!variants || typeof variants !== 'object' || !Object.prototype.hasOwnProperty.call(variants, name)) return undefined
    const value = variants[name]
    return typeof value === 'boolean' || typeof value === 'string' ? value : undefined
  } catch {
    return undefined
  }
}

/**
 * Properties PostHog evaluates flags against. `app_version` is the desktop
 * version as plain MAJOR.MINOR.PATCH (e.g. "1.5.7") so release conditions can
 * use the semver operators (`app_version` >= 1.5.7). Sent as flag-only person
 * properties (no person profile is created; person_profiles stays
 * identified_only) and registered as a super property for events.
 */
export function flagPersonProperties(): { app_version: string } {
  const raw = String(import.meta.env.VITE_APP_VERSION || '').trim().replace(/^v/i, '')
  return { app_version: raw || 'unknown' }
}

type FlagPropsTarget = {
  register?: (props: Properties) => void
  setPersonPropertiesForFlags?: (props: Properties, reload?: boolean) => void
}

function applyFlagProperties(target: FlagPropsTarget) {
  try {
    const props = flagPersonProperties()
    target.register?.({ ...props, ...runtimeProperties() })
    // reload=false: callers either run before the first flag request (loaded) or reload right after.
    target.setPersonPropertiesForFlags?.(props, false)
  } catch { /* analytics cannot break the app */ }
}

function enableFlagNetwork() {
  flagsNetworkEnabled = true
  applyFlagProperties(posthog)
  try {
    posthog.set_config?.({ advanced_disable_flags: false })
    posthog.featureFlags?.setReloadingPaused?.(false)
    posthog.reloadFeatureFlags?.()
  } catch { /* analytics cannot break settings */ }
  notifyRemoteFlags()
}

function disableFlagNetwork() {
  flagsNetworkEnabled = false
  try {
    posthog.set_config?.({ advanced_disable_flags: true })
    posthog.featureFlags?.setReloadingPaused?.(true)
  } catch { /* analytics cannot break settings */ }
  notifyRemoteFlags()
}

/** Never let analytics failures change a successful product operation. */
export function captureBusinessEvent(name: string, properties: Properties = {}): boolean {
  if (!initialized || !isAnalyticsEnabled()) return false
  try {
    return posthog.capture(name, {
      ...properties,
      ...runtimeProperties(),
      schema_version: 2,
      app_version: import.meta.env.VITE_APP_VERSION || 'unknown',
      analytics_environment: import.meta.env.VITE_TELEMETRY_VALIDATION === 'true' ? 'validation' : import.meta.env.DEV ? 'development' : 'production',
      runtime: '__TAURI_INTERNALS__' in window ? 'desktop' : 'web',
      entrypoint: 'ui',
      app_locale: typeof document !== 'undefined' ? document.documentElement.lang : 'unknown',
      system_locale: typeof navigator !== 'undefined' ? navigator.language : 'unknown',
    }) !== undefined
  } catch { return false }
}

/** 是否启用了埋点（已配置 key 且用户未关闭）。 */
export function isAnalyticsEnabled(): boolean {
  if (!POSTHOG_KEY) return false
  if (preferenceOverride !== undefined) return preferenceOverride
  try {
    return localStorage.getItem(OPT_OUT_STORAGE_KEY) !== 'true'
  } catch {
    // an unreadable preference keeps SDK init, capture, flags and identity OFF.
    return false
  }
}

/**
 * 初始化 PostHog。应在应用启动时调用一次。
 * 无 key 时直接返回，不做任何网络请求。
 */
export function initAnalytics(): void {
  if (initialized) return
  // P2: sync the persisted preference (on or off) once the backend is ready.
  publishConsent()
  if (!POSTHOG_KEY) {
    if (import.meta.env.DEV) {
      console.info('[analytics] 未配置 VITE_PUBLIC_POSTHOG_KEY，埋点已禁用')
    }
    return
  }
  if (!isAnalyticsEnabled()) return

  try {
    const id = nativeRuntime().distinct_id
    posthog.init(POSTHOG_KEY, {
    api_host: POSTHOG_HOST,
    // 桌面端从 file:// / 自定义协议加载，cookie 不可靠，统一用 localStorage 持久化匿名 ID
    persistence: 'localStorage',
    ...(id && ANONYMOUS_ID.test(id) ? { bootstrap: { distinctID: id, isIdentifiedID: false } } : {}),
    // 未登录前不创建 person profile，保持匿名；登录后通过 identify 关联（见 ROADMAP Phase 1）
    person_profiles: 'identified_only',
    // Business events are explicit; DOM text may contain filenames or subtitles.
    autocapture: false,
    capture_performance: false,
    // 隐私优先：默认不录屏（PostHog 端也需另行开启）
    disable_session_recording: true,
    // Flag requests exist only while analytics is on. Opt-out never initializes the SDK,
    // and turning analytics off pauses any reload that was already started.
    advanced_disable_flags: false,
    // HashRouter 下手动上报 pageview（见 trackPageview）
    capture_pageview: false,
    capture_pageleave: false,
    property_denylist: ['$current_url', '$referrer', '$initial_current_url', '$initial_referrer'],
    // 尊重用户在本机的关闭偏好
    opt_out_capturing_by_default: !isAnalyticsEnabled(),
    loaded: (ph) => {
      // Runs before posthog-js issues its first flag request, so that request already carries app_version.
      applyFlagProperties(ph)
      try { ph.onFeatureFlags?.((_flags: unknown, _variants: unknown, context?: { errorsLoading?: boolean }) => markRemoteFlagsResponse(context?.errorsLoading)) } catch { /* flags are optional */ }
      publishAnonymousId()
      if (import.meta.env.DEV) ph.debug()
    },
    })
    flagsNetworkEnabled = true
    initialized = true
    watchAnonymousId()
    publishAnonymousId()
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
  for (const listener of preferenceListeners) { try { listener() } catch { /* isolate observers */ } }
  publishConsent()
  if (!initialized && enabled) initAnalytics()
  if (!initialized) return
  try {
    if (enabled) {
      posthog.opt_in_capturing()
      publishAnonymousId()
      if (!flagsNetworkEnabled) enableFlagNetwork()
    } else {
      stopCapturing()
    }
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
  publishedDistinctId = ''
  syncSentryUser(null)
  publishAnonymousId()
}

export { posthog }
