import { studioDownloadRequested } from '../../analytics/studio'
import { Link } from 'react-router-dom'
import { RenderJob } from './types'
import { studioApi } from './api'
import { Dialog, ProgressLine } from '../../ui'
export default function ExportHistory({ projectId, jobs, open, onClose }: { projectId: string; jobs: RenderJob[]; open: boolean; onClose: () => void }) {
  return <Dialog open={open} onClose={onClose} title="导出记录" description="保留每次导出的成片与草稿版本。">
    {!jobs.length && <p className="studio-muted">还没有导出记录，选一条成片即可导出。</p>}
    {jobs.map(job => <div key={job.job_id} className="studio-history-row"><b>{job.title}</b><span className="studio-muted">V{job.revision} · {new Date(job.created_at).toLocaleString()}</span>
      {job.status === 'completed' ? <><a className="ac-btn" href={studioApi.video(projectId, job.job_id, true)} download onClick={studioDownloadRequested}>下载成片</a><Link className="studio-link" to={`/project/${projectId}/publish/studio-${job.job_id}`}>发布这版成片</Link>{job.result?.warnings?.map(w => <p className="studio-muted" key={w}>{w}</p>)}</> : job.status === 'failed' ? <p className="studio-error">{job.error}</p> : <><ProgressLine percent={job.percent} /><span className="studio-muted">{job.status === 'queued' ? '排队中' : '正在渲染'} · {job.percent}%</span></>}
    </div>)}
  </Dialog>
}
