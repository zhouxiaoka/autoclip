import { isDesktopMode } from '../utils/desktopMode'
import {
  rememberSuccessfulCheck,
  shouldCheckAutomatically,
  type ProgressSnap,
} from './updateSchedule'

export type DownloadEvent = {
  event: 'Started' | 'Progress' | 'Finished'
  data?: { contentLength?: number; chunkLength?: number }
}

export type AppUpdate = {
  version: string
  body?: string | null
  date?: string | Date | null
  download: (onEvent?: (progress: DownloadEvent) => void) => Promise<void>
  installAndRelaunch: () => Promise<void>
  close: () => Promise<void>
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
    version: update.version,
    body: update.body,
    date: update.date,
    download: (onEvent) => update.download(onEvent),
    installAndRelaunch: async () => {
      await update.install()
      const { relaunch } = await import('@tauri-apps/plugin-process')
      await relaunch()
    },
    close: () => update.close(),
  }
}

let automaticCheck: Promise<AppUpdate | null> | null = null

/** 生产桌面端：已是最新时 24 小时内不再查。上次发现过新版本，或上次检查失败，下次打开会再查。 */
export function maybeCheckForUpdate(): Promise<AppUpdate | null> {
  if (automaticCheck) return automaticCheck
  automaticCheck = runAutomaticCheck().finally(() => { automaticCheck = null })
  return automaticCheck
}

async function runAutomaticCheck(): Promise<AppUpdate | null> {
  if (!import.meta.env.PROD) return null
  if (!(await isDesktopMode())) return null
  let storage: Storage | null = null
  try { storage = localStorage } catch { storage = null }
  if (storage && !shouldCheckAutomatically(storage, Date.now())) return null
  try {
    const update = await checkForUpdate()
    if (storage) rememberSuccessfulCheck(storage, Date.now(), update ? 'available' : 'current')
    return update
  } catch {
    return null
  }
}

export const emptyProgress = (): ProgressSnap => ({ received: 0, total: 0, percent: null })
