export async function isDesktopMode(): Promise<boolean> {
  return Boolean((window as any).__TAURI__ || (window as any).__TAURI_INTERNALS__)
}
