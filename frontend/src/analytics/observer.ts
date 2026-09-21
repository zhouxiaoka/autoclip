import axios from 'axios'
import { apiConfigManager } from '../utils/apiConfig'
import { captureBusinessEvent, isAnalyticsEnabled, onAnalyticsPreferenceChange } from './posthog'
import { WorkflowTracker, type TaskSnapshot } from './workflow'

const storage = {
  getItem: (key: string) => localStorage.getItem(key),
  setItem: (key: string, value: string) => localStorage.setItem(key, value),
  removeItem: (key: string) => localStorage.removeItem(key),
}
export const workflow = new WorkflowTracker(storage, isAnalyticsEnabled, captureBusinessEvent)
onAnalyticsPreferenceChange(() => workflow.clear())

/** Silent, bounded polling. No global historical scan, raw errors or backend-side telemetry. */
export function startWorkflowObserver(): () => void {
  let stopped = false
  let busy = false
  const poll = async () => {
    if (stopped || busy || !isAnalyticsEnabled()) return
    busy = true
    const generation = workflow.generation()
    try {
      if (!apiConfigManager.isReady() && '__TAURI_INTERNALS__' in window) return
      const baseURL = apiConfigManager.getBaseUrl()
      // Sequential requests avoid competing with video processing on small machines.
      for (const w of workflow.list()) {
        if (stopped || !workflow.active(generation)) break
        if (w.settled) continue
        try {
          if (w.kind === 'project') {
            const { data } = await axios.get<TaskSnapshot[]>(`/tasks/project/${encodeURIComponent(w.id)}`, { baseURL, timeout: 5000 })
            if (!stopped && workflow.active(generation) && Array.isArray(data)) workflow.observeTasks(w, data)
          } else if (w.kind === 'export') {
            if (w.seen.includes('finished')) continue
            const { data } = await axios.get(`/projects/${encodeURIComponent(w.projectId!)}/exports/${encodeURIComponent(w.id)}`, { baseURL, timeout: 5000 })
            if (!stopped && workflow.active(generation) && ['completed', 'failed'].includes(data.status)) {
              workflow.emitOnce(w, 'finished', 'publish_export_finished', {
                project_id: w.projectId, export_id: w.id, outcome: data.status,
                telemetry_source: 'backend_export_observed',
              })
            }
          } else {
            if (w.seen.includes('finished')) continue
            const { data } = await axios.get(`/${w.kind}/tasks/${encodeURIComponent(w.id)}`, { baseURL, timeout: 5000 })
            if (!stopped && workflow.active(generation) && ['completed', 'failed'].includes(data.status)) {
              workflow.emitOnce(w, 'finished', 'import_finished', {
                import_id: w.id, source_type: w.kind, outcome: data.status,
                project_id: data.project_id || undefined,
              })
              if (data.status === 'completed' && data.project_id) workflow.watch('project', data.project_id, undefined, w.since)
            }
          }
        } catch { /* Unreachable backend is unknown, never a processing failure. */ }
      }
    } finally { busy = false }
  }
  void poll()
  const timer = window.setInterval(() => { void poll() }, 15000)
  return () => { stopped = true; window.clearInterval(timer) }
}
