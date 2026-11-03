import { useEffect, useRef, useState } from 'react'
import { OFFLINE_RETRY_MS, POLL_MS, createRecoveryController, type ControllerOptions, type RecoveryApi, type RecoveryController, type RecoveryState } from './transcriptionRecovery'

/** React binding of the one recovery controller: state + a poll loop while installing / downloading.
 * `onReady` is read through a ref, so the page's latest continue callback runs when a wait finishes. */
export function useTranscriptionRecovery(api: RecoveryApi, options: ControllerOptions & { pollMs?: number; offlinePollMs?: number } = {}): [RecoveryState, RecoveryController] {
  const ref = useRef<RecoveryController | null>(null)
  const onReady = useRef(options.onReady)
  onReady.current = options.onReady
  const onReport = useRef(options.onReport)
  onReport.current = options.onReport
  if (!ref.current) ref.current = createRecoveryController(api, { ...options, onReady: report => onReady.current?.(report), onReport: report => onReport.current?.(report) })
  const controller = ref.current
  const [state, setState] = useState<RecoveryState>(controller.state)
  useEffect(() => controller.subscribe(setState), [controller])
  // unmount disposes the controller, so an answer still in flight writes nothing and never continues.
  useEffect(() => { controller.activate(); return () => controller.dispose() }, [controller])
  const waiting = state.phase === 'installing' || state.phase === 'downloading'
  const offline = state.phase === 'failed' && !!state.offline // #403: keep polling slowly (first tick after offlinePollMs, A7), continue when back
  useEffect(() => {
    if (!waiting && !offline) return
    let alive = true
    let timer: ReturnType<typeof setTimeout> | undefined
    const tick = async () => {
      const next = await controller.poll()
      if (!alive) return
      if (next.phase === 'installing' || next.phase === 'downloading') timer = setTimeout(tick, options.pollMs ?? POLL_MS)
      else if (next.phase === 'failed' && next.offline) timer = setTimeout(tick, options.offlinePollMs ?? OFFLINE_RETRY_MS)
    }
    if (waiting) void tick()
    else timer = setTimeout(tick, options.offlinePollMs ?? OFFLINE_RETRY_MS)
    return () => { alive = false; if (timer) clearTimeout(timer) }
  }, [waiting, offline, controller, options.pollMs, options.offlinePollMs])
  return [state, controller]
}
