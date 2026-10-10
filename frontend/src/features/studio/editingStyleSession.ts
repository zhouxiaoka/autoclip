import { normalizeRecommendation, recommendationFailed, recommendationTimedOut, type StyleRecommendation } from './editingStyle'

export type StyleSnapshot = {
  key: string
  status: 'idle' | 'loading' | 'ready'
  result: StyleRecommendation | null
  latencyMs: number
}

const idle: StyleSnapshot = { key: '', status: 'idle', result: null, latencyMs: 0 }
let snapshot: StyleSnapshot = idle
let token = 0
let controller: AbortController | undefined
const listeners = new Set<() => void>()

function publish(next: StyleSnapshot) {
  snapshot = next
  for (const listener of listeners) {
    try { listener() } catch { /* one subscriber cannot block the rest */ }
  }
}

export function readStyle(): StyleSnapshot {
  return snapshot
}

export function subscribeStyle(listener: () => void): () => void {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

/** Start one recommendation. A newer key cancels the previous response. */
export function beginStyleRecommendation(key: string, load: (signal: AbortSignal) => Promise<unknown>) {
  if (!key) return
  if (snapshot.key === key && (snapshot.status === 'loading' || snapshot.status === 'ready')) return
  controller?.abort()
  const mine = ++token
  const ac = new AbortController()
  controller = ac
  publish({ key, status: 'loading', result: null, latencyMs: 0 })
  const started = Date.now()
  const killer = setTimeout(() => ac.abort(), 2000)
  load(ac.signal).then(raw => {
    if (mine !== token) return
    const result = normalizeRecommendation(raw) || recommendationFailed()
    publish({ key, status: 'ready', result, latencyMs: Math.max(0, Date.now() - started) })
  }).catch(() => {
    if (mine !== token) return
    const result = ac.signal.aborted ? recommendationTimedOut() : recommendationFailed()
    publish({ key, status: 'ready', result, latencyMs: Math.max(0, Date.now() - started) })
  }).finally(() => clearTimeout(killer))
}

/** Tests reset the module cache. */
export function resetStyleRecommendation() {
  controller?.abort()
  token += 1
  snapshot = idle
}
