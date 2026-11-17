import { useCallback, useRef, useState, type SetStateAction } from 'react'
import type { Draft } from './types'

/** Keep the latest edit visible to asynchronous responses, even before React renders. */
export function useDraftState() {
  const [draft, commit] = useState<Draft | null>(null)
  const current = useRef<Draft | null>(null)
  const setDraft = useCallback((update: SetStateAction<Draft | null>) => {
    const next = typeof update === 'function' ? update(current.current) : update
    current.current = next
    commit(next)
  }, [])
  return [draft, setDraft, current] as const
}
