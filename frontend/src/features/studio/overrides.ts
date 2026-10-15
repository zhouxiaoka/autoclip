import { flagAssigned } from '../../analytics/flags'
import { trackAutoChoiceOverridden } from '../../analytics/studio'

/** Edits of an automatic decision. Titles and scene text never leave this comparison. */
export type OverrideField = 'title' | 'layout' | 'duration' | 'clip_swap' | 'clip_delete'

export type OverrideDraft = {
  title: string
  layout: string
  scenes: { id: string; start: number; end: number }[]
}

const TAKEN_KEY = 'autoclip.output-taken.v1'
const MISSED_KEY = 'autoclip.output-missed.v1'

export function savedDraftOverrides(before: OverrideDraft, after: OverrideDraft): OverrideField[] {
  const fields: OverrideField[] = []
  if (before.title !== after.title) fields.push('title')
  if (before.layout !== after.layout) fields.push('layout')
  const beforeIds = before.scenes.map(scene => scene.id)
  const afterIds = new Set(after.scenes.map(scene => scene.id))
  const removed = beforeIds.filter(id => !afterIds.has(id)).length
  const added = after.scenes.filter(scene => !beforeIds.includes(scene.id)).length
  if (after.scenes.length < before.scenes.length) fields.push('clip_delete')
  else if (removed > 0 && added > 0) fields.push('clip_swap')
  const moved = before.scenes.some(scene => {
    const next = after.scenes.find(item => item.id === scene.id)
    return !!next && (next.start !== scene.start || next.end !== scene.end)
  })
  if (moved) fields.push('duration')
  return fields
}

function readIds(storage: { getItem: (key: string) => string | null }, key: string): string[] {
  try {
    const parsed = JSON.parse(storage.getItem(key) || '[]')
    return Array.isArray(parsed) ? parsed.filter(item => typeof item === 'string') : []
  } catch { return [] }
}

export function markOutputTaken(projectKey: string, storage: { getItem: (key: string) => string | null; setItem: (key: string, value: string) => void } = sessionStorage) {
  if (!projectKey) return
  const ids = new Set(readIds(storage, TAKEN_KEY))
  ids.add(projectKey)
  try { storage.setItem(TAKEN_KEY, JSON.stringify([...ids])) } catch { /* a missed mark can only over-count not_exported */ }
}

export function outputWasTaken(projectKey: string, storage: { getItem: (key: string) => string | null } = sessionStorage) {
  return readIds(storage, TAKEN_KEY).includes(projectKey)
}

/** One leave, after the run has clips and nothing was copied or saved. */
export function takeUnexportedLeave(projectKey: string, view: { createdAt?: string; status?: string; completed: number }, storage: { getItem: (key: string) => string | null; setItem: (key: string, value: string) => void } = sessionStorage): boolean {
  if (!projectKey || !view.createdAt || view.completed <= 0) return false
  if (view.status !== 'completed' && view.status !== 'partial' && view.status !== 'failed') return false
  if (outputWasTaken(projectKey, storage)) return false
  const token = `${projectKey}:${view.createdAt}`
  const noted = readIds(storage, MISSED_KEY)
  if (noted.includes(token)) return false
  try { storage.setItem(MISSED_KEY, JSON.stringify([...noted, token])) } catch { return false }
  return true
}

type LeaveView = { createdAt?: string; status?: string; completed: number }
let leaveRead: (() => LeaveView) | null = null
let leaveProject = ''
let leaveStop: (() => void) | null = null

function stillOnProject(projectId: string) {
  const hash = window.location.hash
  const prefix = `#/project/${projectId}`
  return hash === prefix || hash.startsWith(`${prefix}/`) || hash.startsWith(`${prefix}?`)
}

function emitUnexportedLeave() {
  if (!leaveProject || !leaveRead || !flagAssigned('track_overrides')) return
  if (!takeUnexportedLeave(leaveProject, leaveRead())) return
  trackAutoChoiceOverridden({ field: 'not_exported', stage: 'results_chip' }, true)
}

/** Keep watching after the results view unmounts into the editor of the same project. */
export function followOutputLeave(projectId: string, read: () => LeaveView) {
  if (typeof window === 'undefined') return () => undefined
  leaveRead = read
  if (leaveProject !== projectId) {
    leaveStop?.()
    leaveProject = projectId
    const onHash = () => {
      if (stillOnProject(projectId)) return
      emitUnexportedLeave()
      leaveStop?.()
      leaveStop = null
      leaveProject = ''
    }
    const onHide = () => emitUnexportedLeave()
    window.addEventListener('hashchange', onHash)
    window.addEventListener('pagehide', onHide)
    leaveStop = () => {
      window.removeEventListener('hashchange', onHash)
      window.removeEventListener('pagehide', onHide)
    }
  }
  return () => {
    if (leaveProject === projectId && !stillOnProject(projectId)) {
      emitUnexportedLeave()
      leaveStop?.()
      leaveStop = null
      leaveProject = ''
    }
  }
}
