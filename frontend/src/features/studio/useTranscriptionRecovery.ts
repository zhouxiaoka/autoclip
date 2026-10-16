import { useEffect, useRef, useState } from 'react'
import { createRecoveryController, type ControllerOptions, type RecoveryApi, type RecoveryController, type RecoveryState } from './transcriptionRecovery'

/** React binding of the one recovery controller: state + a poll loop while installing / downloading.
 * `onReady` is read through a ref, so the page's latest continue callback runs when a wait finishes. */
export function useTranscriptionRecovery(api: RecoveryApi, options: ControllerOptions & { pollMs?: number } = {}): [RecoveryState, RecoveryController] {
  const ref = useRef<RecoveryController | null>(null)
  const onReady = useRef(options.onReady)
  onReady.current = options.onReady
  const onReport = useRef(options.onReport)
  onReport.current = options.onReport
  if (!ref.current) ref.current = createRecoveryController(api, { ...options, onReady: report => onReady.current?.(report), onReport: report => onReport.current?.(report) })
  const controller = ref.current
  const [state, setState] = useState<RecoveryState>(controller.state)
  useEffect(() => controller.subscribe(setState), [controller])
  const waiting = state.phase === 'installing' || state.phase === 'downloading'
  useEffect(() => {
    if (!waiting) return
    let alive = true
    let timer: ReturnType<typeof setTimeout> | undefined
    const tick = async () => {
      const next = await controller.poll()
      if (!alive) return
      if (next.phase === 'installing' || next.phase === 'downloading') timer = setTimeout(tick, options.pollMs ?? 2000)
    }
    void tick()
    return () => { alive = false; if (timer) clearTimeout(timer) }
  }, [waiting, controller, options.pollMs])
  return [state, controller]
}
