import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { t } from '../../i18n'
import { Btn, fmtDuration } from '../../ui'
import { trackOutputShare, type VariantProperties } from '../../analytics/studio'
import StudioDownloadLink from './StudioDownloadLink'
import OutputFeedback from './OutputFeedback'
import { Draft, OutputVariant, RenderJob } from './types'
import { studioApi } from './api'
import { outputVariantPublishPath } from './outputVariantPublish'
import { markRatingAsked, shouldAskRating } from './outputShare'
import { platformLabel } from './platformLabel'
import { packagingLabel, packagingFallbackHint } from './packagingLabel'
import PublishKit from './PublishKit'
import './quick-output.css'

const framingHints: Record<NonNullable<OutputVariant['framing']>, string> = {
  speaker: '已按说话人重新取景',
  full_frame: '画面里没有可跟随的人物，保留完整画面',
  full_frame_pending: '人物识别组件准备中，这条先保留完整画面',
  full_frame_captions: '原片自带字幕，保留完整画面以免裁掉字幕',
}

export default function OutputVariantCard({ projectId, variant, draft, job, onRetry, onProduce }: { projectId: string; variant: OutputVariant; draft?: Draft; job?: RenderJob; onRetry: () => void; onProduce: () => void }) {
  const navigate = useNavigate()
  const [asking, setAsking] = useState(false)
  const [coverStamp, setCoverStamp] = useState(0)
  const packaging = draft?.packaging
  const analytics: VariantProperties = {
    strategy_id: variant.strategy_id, framing: variant.framing, template: packaging?.template,
    packaging_style: packaging ? packaging.style || (packaging.template === 'podcast_en' ? 'pop' : 'classic') : undefined,
    outro_applied: job?.result?.outro_applied,
  }
  const completed = variant.status === 'completed' && job?.status === 'completed'
  const outroEnabled = job?.result?.outro_applied ?? job?.brand_outro ?? variant.branding.outro_enabled
  const failed = variant.status === 'failed'
  const onDemand = variant.status === 'on_demand'
  const duration = job?.result?.duration ?? (draft ? draft.scenes.reduce((sum, scene) => sum + scene.end - scene.start, 0) : 0)
  const packagingHint = packaging ? packagingFallbackHint(packaging, job?.result?.warnings, draft?.subtitles !== false) : ''
  const productionDetails = [outroEnabled ? t('包含 Made with AutoClip 片尾') : t('不含品牌片尾'), packaging && packagingLabel(packaging), variant.framing && t(framingHints[variant.framing])].filter(Boolean).join(' · ')
  const downloaded = () => {
    if (!shouldAskRating(projectId)) return
    markRatingAsked(projectId)
    setAsking(true)
  }
  return <article className="ac-card studio-output-card" aria-label={variant.post?.title || draft?.title || t('正在准备成片')}>
    <div className="studio-variant-thumb" title={productionDetails}>{completed && variant.render_job_id ? <video className="studio-variant-video" controls preload="metadata" poster={variant.cover ? studioApi.variantCover(projectId, variant.id, coverStamp) : undefined} src={studioApi.video(projectId, variant.render_job_id)}/> : <span className="play">▷</span>}<span className="ac-tag ac-tag--tl">{platformLabel(variant.strategy_id)}</span>{duration > 0 && <span className="ac-tag ac-tag--br">{fmtDuration(duration)}</span>}{!completed && <span className="ac-tag studio-output-progress" role="status">{failed ? t('生成失败') : onDemand ? t('备选片段 · 需要时再生成') : variant.status === 'preparing' ? t('正在准备取景与包装') : job?.status === 'running' ? t('正在生成') : t('排队生成中')}</span>}</div>
    <div className="ac-card-body">
      {!variant.post && <h2 className="ac-card-title">{draft?.title || t('正在准备成片')}</h2>}
      {variant.trimmed_to_sec && <p className="studio-output-hint">{t('平台上限 {{seconds}} 秒，已在句子结束处截断', { seconds: variant.trimmed_to_sec })}</p>}
      {packagingHint && <p className="studio-output-hint">{packagingHint}</p>}
      <PublishKit projectId={projectId} variant={variant} analytics={analytics} coverStamp={coverStamp} onCoverChanged={() => setCoverStamp(Date.now())} onCopied={() => trackOutputShare(projectId, { share_target: 'copy_caption', ...analytics })}/>
      {failed && <p className="studio-output-hint studio-error">{t(variant.error || job?.error || '这条版本未完成，其他成片不受影响。')}</p>}
      <div className="ac-card-foot"><div className="ac-card-actions">
        {draft && <Btn variant="text" onClick={() => navigate(`/project/${projectId}/studio/${draft.id}`)}>{t('预览与修改')}</Btn>}
        {failed && <Btn variant="text" onClick={onRetry}>{t('重试这条')}</Btn>}
        {onDemand && <Btn variant="text" onClick={onProduce}>{t('生成这条')}</Btn>}
        {completed && variant.render_job_id && <Btn variant="text" onClick={() => navigate(outputVariantPublishPath(projectId, variant))}>{t('发布')}</Btn>}
        {completed && variant.render_job_id && <StudioDownloadLink className="studio-output-download" projectId={projectId} jobId={variant.render_job_id} onSaved={downloaded} variant={analytics}/>}
      </div></div>
      {asking && <OutputFeedback projectId={projectId} variant={analytics} onDone={() => setAsking(false)}/>}
    </div>
  </article>
}
