import type { Workspace } from './types'

/** After the fast network budget, keep probing a still-producing snapshot at this pace. */
export const OFFLINE_RETRY_MS = 10_000

function workInProgress(data: Workspace): boolean {
  // A backup being prepared has no render job yet, and a rendered one is still getting its cover.
  return data.analysis?.status === 'running' || data.jobs.some(j => j.status === 'queued' || j.status === 'running')
    || (data.output_variants || []).some(v => v.status === 'preparing' || v.status === 'queued' || v.status === 'running')
}

// Observe only: retrying this read must never start analysis or rendering.
export async function pollWorkspace(
  read: (signal: AbortSignal) => Promise<Workspace>,
  options: {
    signal: AbortSignal
    onData: (data: Workspace) => void
    onError: (error: unknown) => void
    onSettled: () => void
    intervalMs?: number
    /** Pace after the fast network budget, while the last snapshot is still producing. */
    offlineIntervalMs?: number
  },
) {
  const { signal } = options
  let failures = 0
  let slow = false
  let last: Workspace | null = null
  while (!signal.aborted) {
    let retry = false
    try {
      const data = await read(signal)
      if (signal.aborted) return
      failures = 0
      slow = false
      last = data
      options.onData(data)
      retry = workInProgress(data)
    } catch (error) {
      if (signal.aborted) return
      options.onError(error)
      const status = (error as { response?: { status?: number } })?.response?.status
      // HTTP errors require a new user/focus refresh. Network interruptions get
      // at most two additional fast attempts. If those still fail and the last
      // snapshot was producing, a slow probe continues so a relaunched backend
      // can replace that frame. No snapshot yet: stop, same as before.
      if (!status && ++failures < 3) {
        retry = true
        slow = false
      } else if (!status && last && workInProgress(last)) {
        retry = true
        slow = true
      }
    } finally {
      if (!signal.aborted) options.onSettled()
    }
    if (!retry || signal.aborted) return
    const delay = slow
      ? (options.offlineIntervalMs ?? OFFLINE_RETRY_MS)
      : (options.intervalMs ?? 3000) * Math.max(1, failures)
    await new Promise<void>(resolve => {
      const finish = () => { clearTimeout(timer); signal.removeEventListener('abort', finish); resolve() }
      const timer = setTimeout(finish, delay)
      signal.addEventListener('abort', finish, { once: true })
      if (signal.aborted) finish()
    })
  }
}
