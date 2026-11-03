/**
 * 应用生命周期埋点 + 全局属性（super properties）。
 *
 * - 全局属性：app_version / os / arch / locale，注册后每条事件自动携带，
 *   方便按"版本 / 系统 / 架构"切片分析（排查"某版本在某系统失败率高"等）。
 * - 生命周期事件：
 *   - app_installed：本设备首次启动（= 装机量代理指标）
 *   - app_opened：每次启动（PostHog 据此自动算 DAU / 留存）
 *   - app_updated：版本号较上次变化
 */
import { getVersion } from '@tauri-apps/api/app'
import { posthog, captureBusinessEvent, isAnalyticsEnabled } from './posthog'
import { runtimeProperties } from './runtime'

const INSTALL_FLAG_KEY = 'autoclip.analytics.installed'
const LAST_VERSION_KEY = 'autoclip.analytics.lastVersion'
const SESSION_COUNT_KEY = 'autoclip.analytics.sessionCount'

async function getAppVersion(): Promise<string> {
  try {
    return await getVersion()
  } catch {
    // 非 Tauri 环境（如浏览器里跑 vite dev）取不到版本
    return import.meta.env.VITE_APP_VERSION || 'unknown'
  }
}

function readInt(key: string): number {
  try {
    return parseInt(localStorage.getItem(key) || '0', 10) || 0
  } catch {
    return 0
  }
}

function safeSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* ignore */
  }
}

export interface RuntimeInfo { version: string; os: string; arch: string; locale: string }
let runtimeInfo: RuntimeInfo = { version: import.meta.env.VITE_APP_VERSION || 'unknown', ...runtimeProperties(), locale: typeof navigator !== 'undefined' ? navigator.language : '' }

/** 启动后缓存的运行环境（版本 / 系统 / 架构），供反馈等场景复用；不依赖埋点是否开启。 */
export function getRuntimeInfo(): RuntimeInfo {
  return { ...runtimeInfo, locale: document.documentElement.lang || runtimeInfo.locale }
}

/**
 * 注册全局属性并上报启动相关生命周期事件。
 * 在 initAnalytics() 之后调用一次。posthog 未初始化时仅缓存运行环境。
 */
export async function trackLaunch(): Promise<void> {
  const appVersion = await getAppVersion()
  const { os, arch } = runtimeProperties()
  const locale = document.documentElement.lang || navigator.language
  runtimeInfo = { version: appVersion, os, arch, locale }

  if (!isAnalyticsEnabled() || typeof posthog?.register !== 'function') return

  // 全局属性：后续每条事件自动携带
  try {
    posthog.register({
      app_version: appVersion,
      os,
      arch,
      app_locale: locale,
      analytics_environment: import.meta.env.DEV ? 'development' : 'production',
    })
  } catch { return }

  // 会话计数
  const sessionCount = readInt(SESSION_COUNT_KEY) + 1
  safeSet(SESSION_COUNT_KEY, String(sessionCount))

  // 首次安装
  let isInstalled = false
  try {
    isInstalled = localStorage.getItem(INSTALL_FLAG_KEY) === 'true'
  } catch {
    /* ignore */
  }
  if (!isInstalled) {
    if (captureBusinessEvent('app_installed', { app_version: appVersion, os, arch })) safeSet(INSTALL_FLAG_KEY, 'true')
  }

  // 版本更新
  let lastVersion: string | null = null
  try {
    lastVersion = localStorage.getItem(LAST_VERSION_KEY)
  } catch {
    /* ignore */
  }
  if (lastVersion && lastVersion !== appVersion) {
    captureBusinessEvent('app_updated', { from_version: lastVersion, to_version: appVersion })
  }
  safeSet(LAST_VERSION_KEY, appVersion)

  // 每次启动
  captureBusinessEvent('app_opened', { app_version: appVersion, session_number: sessionCount })
}
