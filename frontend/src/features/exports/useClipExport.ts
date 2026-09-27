import { useCallback, useEffect, useRef, useState } from 'react'
import { projectApi } from '../../services/api'
import { pollExportJob } from './pollExportJob'

export type ClipExportOptions = Parameters<typeof projectApi.startClipExport>[2]

export function useClipExport(projectId: string, clipId: string) {
  const controller = useRef<AbortController | null>(null)
  const [exporting, setExporting] = useState(false)
  const [percent, setPercent] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<{ jobId: string; warnings?: string[] } | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  const reset = useCallback(() => {
    if (controller.current) return
    setError(null)
    setResult(null)
    setPercent(0)
  }, [])

  const start = async (options: ClipExportOptions) => {
    if (controller.current) return
    const run = new AbortController()
    controller.current = run
    setExporting(true)
    setError(null)
    setResult(null)
    setPercent(5)
    try {
      const started = await projectApi.startClipExport(projectId, clipId, options)
      run.signal.throwIfAborted()
      if (!started.ok || !started.job_id) throw new Error('未能创建导出任务')
      const job = await pollExportJob(
        () => projectApi.getExportJob(projectId, started.job_id, run.signal),
        { signal: run.signal, onProgress: setPercent },
      )
      setResult({ jobId: started.job_id, warnings: job.result?.warnings })
    } catch (err: unknown) {
      if (run.signal.aborted) return
      const failure = err as { response?: { data?: { detail?: string } }; message?: string }
      setError(failure?.response?.data?.detail || failure?.message || '导出失败')
    } finally {
      if (controller.current === run) controller.current = null
      if (!run.signal.aborted) setExporting(false)
    }
  }

  return { exporting, percent, error, result, start, reset }
}
