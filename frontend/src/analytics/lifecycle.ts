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
import { posthog } from './posthog'

const INSTALL_FLAG_KEY = 'autoclip.analytics.installed'
const LAST_VERSION_KEY = 'autoclip.analytics.lastVersion'
const SESSION_COUNT_KEY = 'autoclip.analytics.sessionCount'

/** 从 webview 的 UA 粗略解析操作系统，避免引入需要改 Rust 侧的 plugin-os 依赖。 */
function detectOS(): string {
  const ua = navigator.userAgent
  if (/Mac/i.test(ua)) return 'macos'
  if (/Win/i.test(ua)) return 'windows'
  if (/Linux/i.test(ua)) return 'linux'
  return 'unknown'
}

/** 粗略解析 CPU 架构（用于区分 Intel / Apple Silicon 等）。 */
function detectArch(): string {
  const ua = navigator.userAgent
  if (/arm64|aarch64/i.test(ua)) return 'arm64'
  if (/x86_64|x64|Win64|WOW64|Intel/i.test(ua)) return 'x64'
  return 'unknown'
}

async function getAppVersion(): Promise<string> {
  try {
    return await getVersion()
  } catch {
    // 非 Tauri 环境（如浏览器里跑 vite dev）取不到版本
    return 'unknown'
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
let runtimeInfo: RuntimeInfo = { version: 'unknown', os: detectOS(), arch: detectArch(), locale: typeof navigator !== 'undefined' ? navigator.language : '' }

/** 启动后缓存的运行环境（版本 / 系统 / 架构），供反馈等场景复用；不依赖埋点是否开启。 */
export function getRuntimeInfo(): RuntimeInfo {
  return runtimeInfo
}

/**
 * 注册全局属性并上报启动相关生命周期事件。
 * 在 initAnalytics() 之后调用一次。posthog 未初始化时仅缓存运行环境。
 */
export async function trackLaunch(): Promise<void> {
  const version = await getAppVersion()
  const os = detectOS()
  const arch = detectArch()
  const locale = navigator.language
  runtimeInfo = { version, os, arch, locale }

  if (typeof posthog?.register !== 'function') return

  // 全局属性：后续每条事件自动携带
  posthog.register({
    app_version: version,
    os,
    arch,
    app_locale: locale,
  })

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
    posthog.capture('app_installed', { version, os, arch })
    safeSet(INSTALL_FLAG_KEY, 'true')
  }

  // 版本更新
  let lastVersion: string | null = null
  try {
    lastVersion = localStorage.getItem(LAST_VERSION_KEY)
  } catch {
    /* ignore */
  }
  if (lastVersion && lastVersion !== version) {
    posthog.capture('app_updated', { from_version: lastVersion, to_version: version })
  }
  safeSet(LAST_VERSION_KEY, version)

  // 每次启动
  posthog.capture('app_opened', { version, session_number: sessionCount })
}
