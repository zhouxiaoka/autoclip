import type { ImportOptions } from './types'
import { isVideoFile } from './pasteStart'

export type BatchStatus = 'waiting' | 'uploading' | 'submitted' | 'invalid' | 'blocked' | 'unknown' | 'failed' | 'cancelled'
export type BatchItem = {
  id: number; file: File; subtitle: File | null; status: BatchStatus; projectId?: string
  duration: number | null; window: 'review' | 'full' | 'first'; issue?: string
}
export type BatchSettings = { options: ImportOptions; platforms: string[] }
export type BatchOutcome = { projectId: string } | { issue: string; status: 'blocked' | 'unknown' | 'failed' }

/** Project IDs are opaque single path segments; malformed replies cannot release the next upload. */
export function isBatchProjectId(value: unknown): value is string {
  return typeof value === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(value)
}

/** Window-only queue. A lost initial POST response is not an idempotent retry contract. */
export class BatchImportQueue {
  items: BatchItem[] = []
  settings: BatchSettings | null = null
  running = false
  private paused = false
  private nextId = 0
  private listeners = new Set<() => void>()
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener) } }
  notify = () => { for (const listener of this.listeners) listener() }
  add(files: File[], settings: BatchSettings) {
    if (this.running || this.items.length) return
    this.settings = { options: { ...settings.options, source_window: null }, platforms: [...settings.platforms] }
    this.items = files.map(file => ({ id: ++this.nextId, file, subtitle: null, duration: null, window: 'review',
      status: isVideoFile(file) && file.size > 0 ? 'waiting' : 'invalid', issue: isVideoFile(file) && file.size > 0 ? undefined : 'batchImport.invalid' }))
    this.notify()
  }
  change(id: number, changes: Partial<Pick<BatchItem, 'subtitle' | 'window' | 'duration'>>) {
    if (this.running) return
    this.items = this.items.map(item => item.id === id && ['waiting', 'blocked'].includes(item.status) ? { ...item, ...changes, status: 'waiting', issue: undefined } : item)
    this.notify()
  }
  cancel(id: number) {
    this.items = this.items.map(item => item.id === id && ['waiting', 'blocked'].includes(item.status) ? { ...item, status: 'cancelled' } : item)
    this.notify()
  }
  pause = () => { this.paused = true; this.notify() }
  maySubmit = () => !this.paused
  clear() { if (this.running) return; this.items = []; this.settings = null; this.notify() }
  async start(worker: (item: BatchItem, settings: BatchSettings) => Promise<BatchOutcome>) {
    if (this.running || !this.settings) return
    this.running = true; this.paused = false; this.notify()
    const settings = { options: { ...this.settings.options }, platforms: [...this.settings.platforms] }
    try {
      for (const selected of this.items) {
        if (this.paused) break
        const item = this.items.find(value => value.id === selected.id)!
        if (!['waiting', 'blocked'].includes(item.status)) continue
        // Lock immediately, including the readiness probe; clicks cannot duplicate a POST.
        this.items = this.items.map(value => value.id === item.id ? { ...value, status: 'uploading', issue: undefined } : value)
        this.notify()
        let outcome: BatchOutcome
        try { outcome = await worker({ ...item }, settings) }
        catch { outcome = { status: 'unknown', issue: 'batchImport.unknownHint' } }
        if ('projectId' in outcome && !isBatchProjectId(outcome.projectId)) {
          outcome = { status: 'unknown', issue: 'batchImport.unknownHint' }
        }
        this.items = this.items.map(value => value.id !== item.id ? value : 'projectId' in outcome
          ? { ...value, status: 'submitted', projectId: outcome.projectId, issue: undefined }
          : { ...value, ...outcome })
        this.notify()
        // An unresolved submission stops the queue. Never automatically replay it or spend on more files.
        if (!('projectId' in outcome)) break
      }
    } finally { this.running = false; this.notify() }
  }
}

export function batchImportBody(item: BatchItem, settings: BatchSettings, flowId: string, features: object, template: string | undefined): FormData {
  const body = new FormData(), options = settings.options
  body.append('video', item.file)
  body.append('name', item.file.name.replace(/\.[^.]+$/, '').slice(0, 200))
  if (item.subtitle) body.append('subtitle', item.subtitle)
  body.append('goal', options.goal); body.append('language', options.language); body.append('instruction', options.instruction)
  body.append('auto_start', 'true'); body.append('portrait_style', options.portrait_style || 'auto')
  settings.platforms.forEach(platform => body.append('platforms', platform))
  if (options.aspect) body.append('aspect', options.aspect)
  if (options.duration) body.append('duration', String(options.duration))
  if (template) body.append('html_template', template)
  if (item.window === 'first') { body.append('source_window_start', '0'); body.append('source_window_end', '1800') }
  body.append('features', JSON.stringify(features)); body.append('flow_id', flowId)
  // Independent of analytics IDs; browser-level retransmission reuses this same body.
  body.append('import_operation_id', globalThis.crypto.randomUUID())
  return body
}
