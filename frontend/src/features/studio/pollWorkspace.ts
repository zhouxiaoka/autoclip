import type { Workspace } from './types'

// Observe only: retrying this read must never start analysis or rendering.
export async function pollWorkspace(
  read: (signal: AbortSignal) => Promise<Workspace>,
  options: {
    signal: AbortSignal
    onData: (data: Workspace) => void
    onError: (error: unknown) => void
    onSettled: () => void
    intervalMs?: number
  },
) {
  const { signal } = options
  let failures = 0
  while (!signal.aborted) {
    let retry = false
    try {
      const data = await read(signal)
      if (signal.aborted) return
      failures = 0
      options.onData(data)
      retry = data.analysis?.status === 'running' || data.jobs.some(j => j.status === 'queued' || j.status === 'running')
    } catch (error) {
      if (signal.aborted) return
      options.onError(error)
      const status = (error as { response?: { status?: number } })?.response?.status
      // HTTP errors require a new user/focus refresh. Network interruptions get
      // at most two additional attempts; retain the last successful snapshot.
      retry = !status && ++failures < 3
    } finally {
      if (!signal.aborted) options.onSettled()
    }
    if (!retry || signal.aborted) return
    await new Promise<void>(resolve => {
      const finish = () => { clearTimeout(timer); signal.removeEventListener('abort', finish); resolve() }
      const timer = setTimeout(finish, (options.intervalMs ?? 3000) * Math.max(1, failures))
      signal.addEventListener('abort', finish, { once: true })
      if (signal.aborted) finish()
    })
  }
}
