import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Btn, Icon, fmtDuration } from '../../ui'
import { exportPoster, studioApi } from './api'
import { trackOutputPlayed } from '../../analytics/studio'
import { draftExportState, type ExportStatus } from './draftExportState'
import StudioDownloadLink from './StudioDownloadLink'
import { studioPublishPreviewPath } from './outputVariantPublish'
import { Draft, RenderJob, draftDuration, languages } from './types'

const statusLabels: Record<ExportStatus, string> = {
  draft: '待导出', queued: '排队中', rendering: '正在导出',
  ready: '已导出', failed: '导出失败', updated: '已修改 · 需重新导出',
}

export default function DraftResultCard({ projectId, draft, jobs, onEdit, onExport, onHistory, allowExport = true }: {
  projectId: string; draft: Draft; jobs: RenderJob[]
  onEdit: () => void; onExport: () => void; onHistory: () => void; allowExport?: boolean
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { status, completed, active, failure, previous } = draftExportState(draft, jobs)
  const thumbnail = studioApi.thumbnail(projectId, draft.id, draft.revision, completed?.job_id)
  const [failedThumbnail, setFailedThumbnail] = useState('')
  const playedRef = useRef(false)
  const poster = completed && exportPoster(projectId, completed)
  const thumbnailLabel = completed ? t('当前 V{{revision}} 成片画面', { revision: draft.revision }) : t('原片缩略图 · 包装效果以导出为准')
  const language = draft.language === 'source' ? t('原语言') : languages.find(l => l.value === draft.language)?.label ?? draft.language
  const aspect = t(draft.aspect === 'portrait' ? '9:16 竖屏' : draft.aspect === 'landscape' ? '16:9 横屏' : '原画幅')
  const metaLine = [aspect, language].filter(Boolean).join(' · ')
  const statusTag = status !== 'ready' ? `${t(statusLabels[status])}${active ? ` · ${active.percent ?? 0}%` : ''}` : ''

  return <article className="ac-card studio-output-card" aria-label={`${draft.title} · ${t(statusLabels[status])}`} data-draft-id={draft.id} data-draft-status={status}>
    {completed ? <div className="studio-variant-thumb" title={poster ? t('封面') : thumbnailLabel}>
      <video className="studio-variant-video" aria-label={t('播放成片')} controls preload="metadata"
        onPlay={() => { if (!playedRef.current) { playedRef.current = true; trackOutputPlayed(projectId) } }}
        poster={poster || thumbnail} src={studioApi.video(projectId, completed.job_id)} />
      <span className="ac-tag ac-tag--tl">{t('自定义')}</span>
      <span className="ac-tag ac-tag--br">{fmtDuration(completed.result?.duration ?? draftDuration(draft))}</span>
      {statusTag && <span className="ac-tag studio-output-progress" role="status">{statusTag}</span>}
    </div> :
      <button type="button" className="ac-card-thumb studio-thumb studio-variant-thumb" onClick={onEdit}
        aria-label={t('预览 {{title}}', { title: draft.title })} title={thumbnailLabel}>
        {failedThumbnail === thumbnail
          ? <span className="studio-thumbnail-fallback">{t('缩略图暂不可用 · 点击查看')}</span>
          : <img key={thumbnail} src={thumbnail} alt={thumbnailLabel} loading="lazy" onError={() => setFailedThumbnail(thumbnail)} />}
        <span className="play" aria-hidden="true"><span><Icon.Play size={18} /></span></span>
        <span className="ac-tag ac-tag--tl">{t('自定义')}</span>
        <span className="ac-tag ac-tag--br">{fmtDuration(draftDuration(draft))}</span>
        {statusTag && <span className="ac-tag studio-output-progress" role="status">{statusTag}</span>}
      </button>}
    <div className="ac-card-body studio-draft-content">
      <h2 className="ac-card-title">{draft.title}</h2>
      {metaLine && <p className="studio-result-meta">{metaLine}</p>}
      {status === 'failed' && <p className="studio-error">{failure?.error || t('请重试导出，原草稿已保留')}</p>}
      {status === 'ready' && failure && <p className="studio-output-hint">{t('本版曾有导出失败，已完成文件仍可下载。')}</p>}
      {previous && !completed && <button className="studio-link" onClick={onHistory}>{t('查看已导出的 V{{revision}} 旧版', { revision: previous.revision })}</button>}
      <div className="ac-card-foot"><div className={`ac-card-actions${completed ? ' ac-card-actions--with-edit' : ''}`}>
        {completed && <StudioDownloadLink className="studio-output-download" projectId={projectId} jobId={completed.job_id} />}
        {active ? <Btn size="sm" onClick={onHistory}>{t('查看进度')}</Btn>
          : !completed && allowExport && <Btn size="sm" variant="cta" data-testid="draft-export-btn" data-draft-id={draft.id} aria-label={`${t(status === 'failed' ? '重试导出' : '导出成片')} · ${draft.title}`} onClick={onExport}>{t(status === 'failed' ? '重试导出' : '导出成片')}</Btn>}
        {completed
          ? <>
              <Btn size="sm" aria-label={`${t('发布')} · ${draft.title}`} onClick={() => navigate(studioPublishPreviewPath(projectId, draft.id, completed.job_id))}>{t('发布')}</Btn>
              <Btn size="sm" className="studio-card-edit-btn" data-testid="draft-edit-btn" data-draft-id={draft.id} title={t('编辑')} aria-label={`${t('预览与修改')} · ${draft.title}`} onClick={onEdit}><Icon.Edit size={15} /></Btn>
            </>
          : <Btn size="sm" data-testid="draft-edit-btn" data-draft-id={draft.id} aria-label={`${t('预览与修改')} · ${draft.title}`} onClick={onEdit}>{t('预览与修改')}</Btn>}
      </div></div>
    </div>
  </article>
}
