import { apiConfigManager } from '../../utils/apiConfig'

export function isDesktopDownload() {
  return typeof window !== 'undefined' && !!((window as any).__TAURI__ || (window as any).__TAURI_INTERNALS__)
}

/** Save an existing immutable export. No render request or content telemetry. */
export async function saveStudioExport(projectId: string, jobId: string) {
  if (!isDesktopDownload()) throw new Error('Desktop runtime required')
  if (!apiConfigManager.isReady() && !await apiConfigManager.waitForReady()) throw new Error('Backend not ready')
  const base = apiConfigManager.getBaseUrl().replace(/\/$/, '')
  const url = `${base}/studio/${encodeURIComponent(projectId)}/exports/${encodeURIComponent(jobId)}/video?download=true`
  const { invoke } = await import('@tauri-apps/api/core')
  const result = await invoke<{ size_bytes?: number; sizeBytes?: number }>('save_local_download', { url })
  const size = result?.size_bytes ?? result?.sizeBytes ?? 0
  if (!Number.isFinite(size) || size <= 0) throw new Error('Empty media response')
}
