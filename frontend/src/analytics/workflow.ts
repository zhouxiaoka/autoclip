/** Versioned business telemetry. Only explicit UI operations enroll projects. */
export type Properties = Record<string, string | number | boolean | null | undefined>
export type Watch = { kind: 'project' | 'export' | 'bilibili' | 'youtube'; id: string; projectId?: string; since: number; seen: string[]; settled?: boolean }
export const WORKFLOW_KEY = 'autoclip.analytics.workflow.v2'
const TTL = 7 * 86400000
const LIMIT = 50

export function errorCode(error: unknown): string {
  const e = error as { code?: string; response?: { status?: number } } | undefined
  if (e?.response?.status) return `http_${e.response.status}`
  if (e?.code === 'ECONNABORTED' || e?.code === 'ETIMEDOUT') return 'timeout'
  if (e?.code === 'ERR_NETWORK') return 'network'
  return 'unknown'
}

export function utcMillis(value?: string | null): number | undefined {
  if (!value) return undefined
  const n = Date.parse(/Z$|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
  return Number.isFinite(n) ? n : undefined
}

export function routeName(path: string): string {
  const p = path.split(/[?#]/)[0]
  if (/^\/project\/[^/]+\/?$/.test(p)) return '/project/:id'
  return ['/', '/settings'].includes(p) ? p : '/other'
}

export interface TaskSnapshot {
  id: string; task_type: string; status: string; created_at: string
  started_at?: string | null; completed_at?: string | null
}

/** Storage and capture are injected so offline/privacy/replay behavior is testable. */
export class WorkflowTracker {
  private watches: Watch[] = []
  private epoch = 0
  constructor(
    private storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>,
    private enabled: () => boolean,
    private capture: (event: string, properties: Properties) => boolean,
    private now: () => number = Date.now,
  ) {
    try {
      const raw: unknown = JSON.parse(storage.getItem(WORKFLOW_KEY) || '[]')
      if (Array.isArray(raw)) this.watches = raw.filter((w): w is Watch =>
        w && ['project', 'export', 'bilibili', 'youtube'].includes(w.kind) &&
        typeof w.id === 'string' && Number.isFinite(w.since) && Array.isArray(w.seen) &&
        w.seen.every((v: unknown) => typeof v === 'string') && w.seen.length <= 2000 &&
        (w.projectId === undefined || typeof w.projectId === 'string'))
    } catch { /* corrupted/unavailable storage cannot block the application */ }
    this.prune()
  }
  private prune(): void {
    this.watches = this.watches.filter(w => w.since > this.now() - TTL && w.since <= this.now()).slice(-LIMIT)
  }
  private persist(): void {
    try { this.storage.setItem(WORKFLOW_KEY, JSON.stringify(this.watches)) } catch { /* best effort */ }
  }
  clear(): void {
    this.epoch++
    this.watches = []
    try { this.storage.removeItem(WORKFLOW_KEY) } catch { /* best effort */ }
  }
  generation(): number { return this.epoch }
  active(generation: number): boolean { return generation === this.epoch && this.enabled() }
  list(): Watch[] {
    if (!this.enabled()) { this.clear(); return [] }
    this.prune()
    return [...this.watches]
  }
  watch(kind: Watch['kind'], id: string, projectId?: string, since = this.now()): void {
    if (!this.enabled() || !id) return
    this.prune()
    const existing = this.watches.find(w => w.kind === kind && w.id === id)
    if (existing && !existing.settled) return
    if (existing) this.watches = this.watches.filter(w => w !== existing)
    this.watches.push({ kind, id, projectId, since, seen: [] })
    this.prune()
    this.persist()
  }
  emitOnce(w: Watch, key: string, event: string, properties: Properties): void {
    if (!this.enabled() || !this.watches.includes(w) || w.seen.includes(key) || w.seen.length >= 2000) return
    if (this.capture(event, { ...properties, $insert_id: `autoclip-v2:${w.kind}:${w.id}:${key}` })) {
      w.seen.push(key)
      this.persist()
    }
  }
  observeTasks(w: Watch, tasks: TaskSnapshot[]): void {
    const eligible = tasks.filter(t => t.task_type === 'video_processing' && (utcMillis(t.created_at) ?? -1) >= w.since)
    for (const t of eligible) {
      const created = utcMillis(t.created_at)
      if (t.task_type !== 'video_processing' || created === undefined || created < w.since) continue
      const props = { project_id: w.id, task_id: t.id, telemetry_source: 'backend_task_observed' }
      this.emitOnce(w, `${t.id}:observed`, 'processing_task_observed', props)
      // Some workers omit timestamps. Never invent a start or duration for a missed transition.
      const start = utcMillis(t.started_at)
      const end = utcMillis(t.completed_at)
      if (t.status === 'running' || start !== undefined) this.emitOnce(w, `${t.id}:started`, 'processing_started', {
        ...props, occurred_at: new Date(start ?? created).toISOString(),
        time_basis: start === undefined ? 'task_created_at' : 'task_started_at',
      })
      if (['completed', 'failed', 'cancelled'].includes(t.status)) this.emitOnce(w, `${t.id}:finished`, 'processing_finished', {
        ...props, outcome: t.status, occurred_at: end === undefined ? undefined : new Date(end).toISOString(),
        duration_ms: start !== undefined && end !== undefined && end >= start ? end - start : undefined,
      })
    }
    if (eligible.length > 0 && eligible.every(t => w.seen.includes(`${t.id}:finished`))) {
      w.settled = true
      this.persist()
    }
  }
}
