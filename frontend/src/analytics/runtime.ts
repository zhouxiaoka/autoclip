/** Safe, synchronous runtime facts. Tauri injects these before application JS. */
type NativeRuntime = { os?: string; arch?: string; distinct_id?: string }

export function nativeRuntime(): NativeRuntime {
  if (typeof window === 'undefined') return {}
  return (window as Window & { __AUTOCLIP_RUNTIME__?: NativeRuntime }).__AUTOCLIP_RUNTIME__ || {}
}

export function normalizeArch(value?: string): string {
  const arch = typeof value === 'string' ? value.trim().toLowerCase() : ''
  if (arch === 'arm64' || arch === 'aarch64') return 'aarch64'
  if (arch === 'x86_64' || arch === 'amd64' || arch === 'x64') return 'x86_64'
  return 'unknown'
}

export function runtimeProperties(): { os: string; arch: string } {
  const native = nativeRuntime()
  const ua = typeof navigator === 'undefined' ? '' : navigator.userAgent
  const os = native.os === 'macos' || native.os === 'windows' || native.os === 'linux'
    ? native.os : /Mac/i.test(ua) ? 'macos' : /Win/i.test(ua) ? 'windows' : /Linux/i.test(ua) ? 'linux' : 'unknown'
  const arch = native.arch ? normalizeArch(native.arch)
    : /arm64|aarch64/i.test(ua) ? 'aarch64'
      // Mac webviews advertise Intel even on Apple Silicon. Only trust native facts.
      : os !== 'macos' && /x86_64|amd64|x64|Win64|WOW64/i.test(ua) ? 'x86_64' : 'unknown'
  return { os, arch }
}
