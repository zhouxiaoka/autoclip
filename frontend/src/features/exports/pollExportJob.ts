export interface ExportJob {
  job_id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  percent?: number
  error?: string
  result?: { warnings?: string[] }
}

interface PollOptions {
  signal: AbortSignal
  onProgress: (percent: number) => void
  intervalMs?: number
  maxAttempts?: number
}

function wait(ms: number, signal: AbortSignal): Promise<void> {
  signal.throwIfAborted()
  return new Promise((resolve, reject) => {
    const onAbort = () => {
      clearTimeout(timer)
      signal.removeEventListener('abort', onAbort)
      reject(signal.reason)
    }
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', onAbort)
      resolve()
    }, ms)
    signal.addEventListener('abort', onAbort, { once: true })
  })
}

/** Stopping observation does not cancel the server's render job. */
export async function pollExportJob(
  readJob: () => Promise<ExportJob>,
  { signal, onProgress, intervalMs = 1000, maxAttempts = 180 }: PollOptions,
): Promise<ExportJob> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    await wait(intervalMs, signal)
    const job = await readJob()
    signal.throwIfAborted()
    onProgress(job.percent ?? 10)
    if (job.status === 'completed') return job
    if (job.status === 'failed') throw new Error(job.error || '导出失败')
  }
  throw new Error('等待导出结果超时，后台任务可能仍在运行，请稍后在输出目录查看')
}
