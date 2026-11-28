export type ExportDirectoryState = { configuredPath: string | null; effectivePath: string }
export type ExportDirectoryAction = 'get_export_directory' | 'choose_export_directory' | 'reset_export_directory'

/** Only native commands choose a destination; no path is sent from the webview. */
export async function exportDirectory(action: ExportDirectoryAction): Promise<ExportDirectoryState> {
  const { invoke } = await import('@tauri-apps/api/core')
  const value = await invoke<ExportDirectoryState>(action)
  if (!value || typeof value.effectivePath !== 'string' || !value.effectivePath
    || (value.configuredPath !== null && typeof value.configuredPath !== 'string')) {
    throw new Error('export_directory_config_invalid')
  }
  return value
}

export function exportDirectoryIssue(error: unknown): string {
  const code = error instanceof Error ? error.message : String(error)
  if (code === 'export_directory_unavailable') return 'exportFolder.unavailable'
  if (code === 'export_directory_config_invalid' || code === 'export_directory_config_unreadable') return 'exportFolder.readError'
  return 'exportFolder.saveError'
}
