import { useCallback, useEffect, useState } from 'react'
import { studioApi, errorText } from './api'
import { Workspace, emptyWorkspace } from './types'
import { pollWorkspace } from './pollWorkspace'

export function useWorkspace(projectId: string | undefined) {
  const [state, setState] = useState<Workspace>(emptyWorkspace)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [version, setVersion] = useState(0)
  const refresh = useCallback(() => setVersion(v => v + 1), [])
  useEffect(() => {
    if (!projectId) return
    const controller = new AbortController()
    setLoading(true)
    void pollWorkspace(signal => studioApi.get(projectId, signal), {
      signal: controller.signal,
      onData: data => { setState(data); setError('') },
      onError: error => setError(errorText(error)),
      onSettled: () => setLoading(false),
    })
    return () => controller.abort()
  }, [projectId, version])
  useEffect(() => {
    const resume = () => { if (document.visibilityState === 'visible') refresh() }
    window.addEventListener('focus', resume)
    document.addEventListener('visibilitychange', resume)
    return () => {
      window.removeEventListener('focus', resume)
      document.removeEventListener('visibilitychange', resume)
    }
  }, [refresh])
  return { workspace: state, error, loading, refresh }
}
