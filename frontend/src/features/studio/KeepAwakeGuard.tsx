import { useEffect, useState } from 'react'
import { useProjectStore } from '../../store/useProjectStore'
import { getKeepAwakeController } from './keepAwake'

/**
 * Watches the project list and drives keep-awake.
 * Workspace poll also reports via getKeepAwakeController().setSource('workspace:…').
 */
export default function KeepAwakeGuard() {
  const projects = useProjectStore(s => s.projects)

  useEffect(() => {
    getKeepAwakeController().syncProjects(projects)
  }, [projects])

  return null
}

/** Hook for Header / status bar indicator. */
export function useKeepAwakeHeld(): boolean {
  const [held, setHeld] = useState(() => getKeepAwakeController().isHeld())
  useEffect(() => getKeepAwakeController().subscribe(setHeld), [])
  return held
}
