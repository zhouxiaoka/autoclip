import { isDesktopMode } from '../utils/desktopMode'

const LAST_CHECK_KEY = 'autoclip.updater.lastCheckAt'
const INTERVAL_MS = 24 * 60 * 60 * 1000

export type AppUpdate = {
  version: string
  body?: string | null
  date?: string | Date | null
  downloadAndInstall: () => Promise<void>
}

async function loadUpdater() {
  const { check } = await import('@tauri-apps/plugin-updater')
  return check
}

export async function getAppVersion(): Promise<string> {
  if (!(await isDesktopMode())) return import.meta.env.VITE_APP_VERSION || ''
  try {
    const { getVersion } = await import('@tauri-apps/api/app')
    return await getVersion()
  } catch {
    return import.meta.env.VITE_APP_VERSION || ''
  }
}

export async function checkForUpdate(): Promise<AppUpdate | null> {
  if (!(await isDesktopMode())) return null
  const check = await loadUpdater()
  const update = await check()
  if (!update) return null
  return {
    version: update.version, body: update.body, date: update.date,
    downloadAndInstall: () => update.downloadAndInstall(),
  }
}

/** 生产桌面端 24 小时内最多自动检查一次。 */
export async function maybeCheckForUpdate(): Promise<AppUpdate | null> {
  if (!import.meta.env.PROD) return null
  if (!(await isDesktopMode())) return null
  try {
    const last = Number(localStorage.getItem(LAST_CHECK_KEY) || 0)
    if (last && Date.now() - last < INTERVAL_MS) return null
    localStorage.setItem(LAST_CHECK_KEY, String(Date.now()))
  } catch {
    /* ignore quota / private mode */
  }
  try { return await checkForUpdate() } catch { return null }
}

export async function installUpdateAndRelaunch(update: AppUpdate): Promise<void> {
  await update.downloadAndInstall()
  const { relaunch } = await import('@tauri-apps/plugin-process')
  await relaunch()
}
