import { Btn, fmtDuration } from '../../ui'
import { studioApi } from './api'
import { Draft, RenderJob, draftDuration, languages } from './types'
import { draftExportState, ExportStatus } from './draftExportState'

const statusLabels: Record<ExportStatus, string> = {
  draft: '草稿 · 待导出', queued: '排队中', rendering: '正在导出',
  ready: '已导出 · 可下载', failed: '导出失败', updated: '已修改 · 需重新导出',
}

export default function DraftResultCard({ projectId, draft, jobs, onEdit, onExport, onHistory }: {
  projectId: string; draft: Draft; jobs: RenderJob[]
  onEdit: () => void; onExport: () => void; onHistory: () => void
}) {
  const state = draftExportState(draft, jobs)
  const label = statusLabels[state.status]
  const completed = state.completed
  const thumbnail = completed ? studioApi.video(projectId, completed.job_id)
    : `${studioApi.source(projectId)}#t=${draft.scenes[0].start}`
  return <article className="ac-card">
    <button className="ac-card-thumb studio-thumb" onClick={onEdit} aria-label={`预览 ${draft.title}`}>
      <video muted preload="metadata" src={thumbnail} />
      <span className="play">▷</span>
      <span className="ac-tag ac-tag--tl">{draft.origin==='visual-promo'?'推广成片':draft.origin==='visual-highlight'?'精彩高光':'成片草稿'}</span>
      <span className="ac-tag ac-tag--br">{fmtDuration(draftDuration(draft))}</span>
    </button>
    <div className="ac-card-body">
      <h2 className="ac-card-title">{draft.title}</h2>
      <div className={`studio-output-state studio-output-state--${state.status}`} role="status">
        {label}{state.active ? ` · ${state.active.percent ?? 0}%` : ''}
      </div>
      <p className="studio-output-hint">{completed ? `当前 V${draft.revision} 成片画面` : '原片缩略图 · 包装效果以导出为准'}</p>
      <div className="ac-card-desc">{draft.hook||draft.scenes[0].evidence||'保留原声与完整事件'}</div>
      {state.status==='failed' && <p className="studio-output-hint studio-error">{state.failure?.error || '请重试导出，原草稿已保留'}</p>}
      {state.status==='ready' && state.failure && <p className="studio-output-hint">本版曾有导出失败，已完成文件仍可下载。</p>}
      {state.previous && !completed && <button className="studio-link studio-output-hint" onClick={onHistory}>查看已导出的 V{state.previous.revision} 旧版</button>}
      <div className="ac-card-foot">
        <span className="meta">{languages.find(l=>l.value===draft.language)?.label} · V{draft.revision} · {draft.scenes.length} 段</span>
        <div className="ac-card-actions">
          <Btn variant="text" onClick={onEdit}>预览与修改</Btn>
          {completed ? <a className="studio-link" href={studioApi.video(projectId, completed.job_id, true)} download>下载成片</a>
            : state.active ? <Btn variant="text" onClick={onHistory}>查看进度</Btn>
            : <Btn variant="text" onClick={onExport}>{state.status==='failed'?'重试导出':'导出成片'}</Btn>}
        </div>
      </div>
    </div>
  </article>
}
