import { useCallback, useEffect, useState } from 'react'
import { studioApi, errorText } from './api'
import { Workspace, emptyWorkspace } from './types'

export function useWorkspace(projectId: string | undefined) {
  const [state, setState] = useState<Workspace>(emptyWorkspace)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [version, setVersion] = useState(0)
  const refresh = useCallback(() => setVersion(v => v + 1), [])
  useEffect(() => {
    if (!projectId) return
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    setLoading(true)
    const read = async () => {
      try {
        const data = await studioApi.get(projectId, controller.signal)
        if (!controller.signal.aborted) { setState(data); setError('') }
      } catch (e) {
        if (!controller.signal.aborted) setError(errorText(e))
      } finally {
        if (!controller.signal.aborted) { setLoading(false); timer = setTimeout(read, 3000) }
      }
    }
    void read()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [projectId, version])
  return { workspace: state, error, loading, refresh }
}
