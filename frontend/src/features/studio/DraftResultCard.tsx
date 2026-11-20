import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Btn, Icon, fmtDuration } from '../../ui'
import { studioApi } from './api'
import { draftExportState, type ExportStatus } from './draftExportState'
import StudioDownloadLink from './StudioDownloadLink'
import { ExportCoverButton } from './ExportCover'
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
  const thumbnailLabel = completed ? t('当前 V{{revision}} 成片画面', { revision: draft.revision }) : t('原片缩略图 · 包装效果以导出为准')
  const language = draft.language === 'source' ? t('原语言') : languages.find(l => l.value === draft.language)?.label ?? draft.language
  const aspect = t(draft.aspect === 'portrait' ? '9:16 竖屏' : draft.aspect === 'landscape' ? '16:9 横屏' : '原画幅')
  const kind = draft.origin === 'visual-promo' ? t('推广成片') : draft.origin === 'visual-highlight' ? t('精彩高光') : ''
  const description = draft.hook || draft.scenes[0]?.evidence

  return <article className="ac-card studio-output-card" aria-label={draft.title}>
    {completed ? <div className="studio-variant-thumb" title={thumbnailLabel}>
      <video className="studio-variant-video" aria-label={t('播放成片')} controls preload="metadata"
        poster={thumbnail} src={studioApi.video(projectId, completed.job_id)} />
      <span className="ac-tag ac-tag--br">{fmtDuration(completed.result?.duration ?? draftDuration(draft))}</span>
    </div> :
      <button type="button" className="ac-card-thumb studio-thumb studio-variant-thumb" onClick={onEdit}
        aria-label={t('预览 {{title}}', { title: draft.title })} title={thumbnailLabel}>
        {failedThumbnail === thumbnail
          ? <span className="studio-thumbnail-fallback">{t('缩略图暂不可用 · 点击查看')}</span>
          : <img key={thumbnail} src={thumbnail} alt={thumbnailLabel} loading="lazy" onError={() => setFailedThumbnail(thumbnail)} />}
        <span className="play" aria-hidden="true"><span><Icon.Play size={18} /></span></span>
        <span className="ac-tag ac-tag--br">{fmtDuration(draftDuration(draft))}</span>
      </button>}
    <div className="ac-card-body studio-draft-content">
      <div className="studio-draft-status" data-status={status} role="status">
        {t(statusLabels[status])}{active && ` · ${active.percent ?? 0}%`}
      </div>
      <h2 className="ac-card-title">{draft.title}</h2>
      <p className="studio-draft-meta">{[kind, aspect, language, `V${draft.revision}`, t('{{count}} 段', { count: draft.scenes.length })].filter(Boolean).join(' · ')}</p>
      {description && description !== draft.title && <p className="studio-draft-description" title={description}>{description}</p>}
      {status === 'failed' && <p className="studio-error">{failure?.error || t('请重试导出，原草稿已保留')}</p>}
      {status === 'ready' && failure && <p>{t('本版曾有导出失败，已完成文件仍可下载。')}</p>}
      {previous && !completed && <button className="studio-link" onClick={onHistory}>{t('查看已导出的 V{{revision}} 旧版', { revision: previous.revision })}</button>}
      <div className="ac-card-foot"><div className="ac-card-actions">
        {completed && <StudioDownloadLink className="studio-output-download" projectId={projectId} jobId={completed.job_id} />}
        {active ? <Btn size="sm" onClick={onHistory}>{t('查看进度')}</Btn>
          : !completed && allowExport && <Btn size="sm" variant="cta" onClick={onExport}>{t(status === 'failed' ? '重试导出' : '导出成片')}</Btn>}
        <Btn size="sm" onClick={onEdit}>{t('预览与修改')}</Btn>
      </div></div>
      {completed && <details className="studio-publish-tools">
        <summary>{t('发布工具')}</summary>
        <ExportCoverButton projectId={projectId} job={completed} />
        <Btn size="sm" variant="cta" onClick={() => navigate(`/project/${projectId}/publish/studio-${completed.job_id}`)}>{t('发布')}</Btn>
      </details>}
    </div>
  </article>
}
