import type { Draft, RenderJob } from './types'

export type ExportStatus = 'draft' | 'queued' | 'rendering' | 'ready' | 'failed' | 'updated'

/** Match immutable export snapshots to the exact saved draft version. */
export function draftExportState(draft: Pick<Draft, 'id' | 'revision'>, jobs: RenderJob[]) {
  const timestamp = (job: RenderJob) => Date.parse(job.created_at) || 0
  const related = jobs.filter(j => j.draft_id === draft.id).sort((a, b) => timestamp(b) - timestamp(a))
  const current = related.filter(j => j.revision === draft.revision)
  const completed = current.find(j => j.status === 'completed')
  const active = current.find(j => j.status === 'queued' || j.status === 'running')
  const failure = current.find(j => j.status === 'failed')
  const previous = related.find(j => j.revision < draft.revision && j.status === 'completed')
  const status: ExportStatus = active ? (active.status === 'queued' ? 'queued' : 'rendering')
    : completed ? 'ready' : failure ? 'failed' : previous ? 'updated' : 'draft'
  return { status, completed, active, failure, previous }
}
