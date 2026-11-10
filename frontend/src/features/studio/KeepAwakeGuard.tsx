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

/**
 * Header pill. True only while some source is still producing and the native
 * lock is confirmed on. A failed release is unknown: the pill stays off, and
 * this hook does not report that the machine is still producing or that sleep
 * is already allowed.
 */
export function useKeepAwakeHeld(): boolean {
  const [show, setShow] = useState(() => getKeepAwakeController().showsActivityLock())
  useEffect(() => getKeepAwakeController().subscribe(setShow), [])
  return show
}
