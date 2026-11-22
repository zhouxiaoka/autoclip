import type { Draft, RenderJob } from './types'

export type ExportStatus = 'draft' | 'queued' | 'rendering' | 'ready' | 'failed' | 'updated'

/** Match immutable export snapshots to the exact saved draft version. */
export function draftExportState(
  draft: Pick<Draft, 'id' | 'revision' | 'aspect' | 'html_template'>,
  jobs: RenderJob[],
  standalone = true,
) {
  const timestamp = (job: RenderJob) => Date.parse(job.created_at) || 0
  const related = jobs.filter(j => j.draft_id === draft.id).sort((a, b) => timestamp(b) - timestamp(a))
  const design = standalone && draft.aspect === 'portrait' ? draft.html_template : null
  // A restored plan can supply a missing design without incrementing the draft revision.
  const isCurrent = (job: RenderJob) => job.revision === draft.revision &&
    (!design || (job.requested_template ?? job.html_template ?? 'classic') === design)
  const current = related.filter(isCurrent)
  const completed = current.find(j => j.status === 'completed')
  const active = current.find(j => j.status === 'queued' || j.status === 'running')
  const failure = current.find(j => j.status === 'failed')
  const previous = related.find(j => j.status === 'completed' && j.revision <= draft.revision && !isCurrent(j))
  const status: ExportStatus = active ? (active.status === 'queued' ? 'queued' : 'rendering')
    : completed ? 'ready' : failure ? 'failed' : previous ? 'updated' : 'draft'
  return { status, completed, active, failure, previous }
}
