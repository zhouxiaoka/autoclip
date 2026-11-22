import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Btn, fmtDuration } from '../../ui'
import { flagAssigned } from '../../analytics/flags'
import { trackOutputShare, type VariantProperties } from '../../analytics/studio'
import { exportPoster, studioApi } from './api'
import { PublishClip } from '../../pages/PublishClipPage'
import { outputVariantPublishQuery } from './outputVariantPublish'
import { platformLabel } from './platformLabel'
import PublishKit from './PublishKit'
import type { Draft, OutputVariant, RenderJob } from './types'
import './quick-output.css'

export default function StudioPublishPreview({ projectId, job, draft, variant, analytics, onEdit, onRefresh }: {
  projectId: string; job: RenderJob; draft?: Draft; variant?: OutputVariant; analytics: VariantProperties; onEdit?: () => void; onRefresh: () => void
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [editedPost, setEditedPost] = useState<typeof job.post>()
  const [coverStamp, setCoverStamp] = useState(0)
  const coverChanged = useCallback(() => { setCoverStamp(Date.now()); onRefresh() }, [onRefresh])
  const post = editedPost ?? variant?.post ?? job.post ?? { title: job.title, description: draft && job.revision === draft.revision ? draft.hook || '' : '', tags: [] }
  const poster = variant && (variant.cover || coverStamp) ? studioApi.variantCover(projectId, variant.id, coverStamp) : exportPoster(projectId, job, coverStamp)
  return <div className="ac-page studio-editor-page">
    <button type="button" className="ac-back" onClick={() => navigate(`/project/${projectId}`)}>{t('‹ 返回项目')}</button>
    <header className="studio-editor-head"><h1 className="ac-title">{t('发布')}</h1>
      <span className="studio-muted">{[variant && platformLabel(variant.strategy_id), `V${job.revision}`, fmtDuration(job.result?.duration || 0)].filter(Boolean).join(' · ')}</span>
    </header>
    <div className="studio-publish-grid">
      <section className="studio-publish-player" aria-label={t('成片')}>
        <video width={job.result?.width} height={job.result?.height} controls playsInline preload="metadata" poster={poster} src={studioApi.video(projectId, job.job_id)} aria-label={t('播放成片')} />
        {onEdit && <Btn size="sm" onClick={onEdit}>{t('预览与修改')}</Btn>}
      </section>
      <aside className="studio-publish-panel" aria-label={t('发布工具')}>
        <PublishKit projectId={projectId} job={job} variant={variant} post={post} onPostChange={value => { setEditedPost(value); onRefresh() }}
          coverStamp={coverStamp} onCoverChanged={coverChanged} analytics={analytics}
          onCopied={() => trackOutputShare(projectId, { share_target: 'copy_caption', ...analytics })}
          onCombined={() => { if (flagAssigned('publish_pack_v2')) trackOutputShare(projectId, { share_target: 'copy_and_save', ...analytics }) }} />
        <PublishClip projectId={projectId} clipId={`studio-${job.job_id}`} search={variant ? outputVariantPublishQuery(variant) : ''} preparedPost={post} />
      </aside>
    </div>
  </div>
}
