import { useCallback, useEffect, useRef, useState } from 'react'
import { apiConfigManager } from '../../utils/apiConfig'
import { studioApi, errorText } from './api'
import { Workspace, emptyWorkspace } from './types'
import { observeWorkspace, workInProgress } from './pollWorkspace'
import { getKeepAwakeController } from './keepAwake'

export function useWorkspace(projectId: string | undefined) {
  const [state, setState] = useState<Workspace>(emptyWorkspace)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  // True once the first response arrived; `loading` turns true again on every refresh.
  const [loaded, setLoaded] = useState(false)
  const [version, setVersion] = useState(0)
  const shown = useRef(projectId)
  const refresh = useCallback(() => setVersion(v => v + 1), [])
  useEffect(() => {
    if (!projectId) return
    const controller = new AbortController()
    setLoading(true)
    if (shown.current !== projectId) { shown.current = projectId; setLoaded(false); setState(emptyWorkspace) }
    void observeWorkspace(signal => studioApi.get(projectId, signal), {
      signal: controller.signal,
      onData: data => {
        setState(data); setError(''); setLoaded(true)
        getKeepAwakeController().setSource(`workspace:${projectId}`, workInProgress(data))
      },
      onError: error => setError(errorText(error)),
      onSettled: () => setLoading(false),
      // backend-started updates the API port and notifies listeners. Re-arm even
      // when the fast network budget is already spent, without waiting for focus.
      subscribeRestart: onRestart => apiConfigManager.addListener(config => {
        if (config.isReady) onRestart()
      }),
    })
    return () => {
      controller.abort()
      getKeepAwakeController().setSource(`workspace:${projectId}`, false)
    }
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
  return { workspace: state, error, loading, loaded, refresh }
}
