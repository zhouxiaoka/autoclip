import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { t } from '../../i18n'
import { Btn, Icon, fmtDuration } from '../../ui'
import { trackOutputPlayed, type VariantProperties } from '../../analytics/studio'
import StudioDownloadLink from './StudioDownloadLink'
import OutputFeedback from './OutputFeedback'
import { Draft, OutputVariant, RenderJob, languages } from './types'
import { exportPoster, studioApi } from './api'
import { outputAnalytics, studioPublishPreviewPath } from './outputVariantPublish'
import { markRatingAsked, shouldAskRating } from './outputShare'
import { platformLabel } from './platformLabel'
import { packagingLabel, packagingFallbackHint } from './packagingLabel'
import './quick-output.css'
import { effectiveSubtitles } from './subtitleState'
import { readableFailure, failureStep, BILLING_GUIDANCE } from './failureAction'

const framingHints: Record<NonNullable<OutputVariant['framing']>, string> = {
  speaker: '已按说话人重新取景',
  full_frame: '画面里没有可跟随的人物，保留完整画面',
  full_frame_pending: '人物识别组件准备中，这条先保留完整画面',
  full_frame_captions: '原片自带字幕，保留完整画面以免裁掉字幕',
}

const PORTRAIT_STRATEGIES = new Set(['douyin', 'tiktok', 'instagram_reels', 'youtube_shorts', 'xiaohongshu'])
const LANDSCAPE_STRATEGIES = new Set(['bilibili', 'youtube_long'])

function variantAspectLabel(variant: OutputVariant, draft?: Draft, job?: RenderJob): string {
  if (draft?.aspect) {
    return t(draft.aspect === 'portrait' ? '9:16 竖屏' : draft.aspect === 'landscape' ? '16:9 横屏' : '原画幅')
  }
  if (job?.result?.width && job?.result?.height) {
    return t(job.result.height > job.result.width ? '9:16 竖屏' : '16:9 横屏')
  }
  if (PORTRAIT_STRATEGIES.has(variant.strategy_id)) return t('9:16 竖屏')
  if (LANDSCAPE_STRATEGIES.has(variant.strategy_id)) return t('16:9 横屏')
  return t('原画幅')
}

export default function OutputVariantCard({ projectId, variant, draft, job, onRetry, onProduce, onViewed, recommendation, billable }: { projectId: string; variant: OutputVariant; draft?: Draft; job?: RenderJob; onRetry: () => void; onProduce: () => void; onViewed?: () => void; recommendation?: { recommended_template?: VariantProperties['recommended_template']; accepted_recommendation?: boolean }; billable?: boolean }) {
  const navigate = useNavigate()
  const post = variant.post
  const [asking, setAsking] = useState(false)
  const playedRef = useRef(false)
  const packaging = draft?.packaging
  const analytics = outputAnalytics(variant, draft, job, recommendation)
  const completed = variant.status === 'completed' && job?.status === 'completed'
  const outroEnabled = job?.result?.outro_applied ?? job?.brand_outro ?? variant.branding.outro_enabled
  const failed = variant.status === 'failed'
  const onDemand = variant.status === 'on_demand'
  const duration = job?.result?.duration ?? (draft ? draft.scenes.reduce((sum, scene) => sum + scene.end - scene.start, 0) : 0)
  const title = post?.title || draft?.title || t('正在准备成片')
  const aspect = variantAspectLabel(variant, draft, job)
  const language = draft?.language
    ? (draft.language === 'source' ? t('原语言') : languages.find(l => l.value === draft.language)?.label ?? draft.language)
    : ''
  const metaLine = [aspect, language].filter(Boolean).join(' · ')
  const hasEdit = completed && !!variant.render_job_id && !!draft
  const packagingHint = packaging ? packagingFallbackHint(packaging, job?.result?.warnings, effectiveSubtitles(draft)) : ''
  const productionDetails = [outroEnabled ? t('包含 Made with AutoClip 片尾') : t('不含品牌片尾'), packaging && packagingLabel(packaging), variant.framing && t(framingHints[variant.framing])].filter(Boolean).join(' · ')
  const downloaded = () => {
    onViewed?.()
    if (!shouldAskRating(projectId)) return
    markRatingAsked(projectId)
    setAsking(true)
  }
  return <article className="ac-card studio-output-card" aria-label={title}>
    <div className="studio-variant-thumb" title={productionDetails}>{completed && variant.render_job_id ? <video className="studio-variant-video" aria-label={t('播放成片')} onPlay={() => { if (!playedRef.current) { playedRef.current = true; trackOutputPlayed(projectId, analytics) } onViewed?.() }} controls preload="metadata" poster={variant.cover ? studioApi.variantCover(projectId, variant.id) : exportPoster(projectId, job)} src={studioApi.video(projectId, variant.render_job_id)}/> : <span className="play">▷</span>}<span className="ac-tag ac-tag--tl">{platformLabel(variant.strategy_id)}</span>{duration > 0 && <span className="ac-tag ac-tag--br">{fmtDuration(duration)}</span>}{!completed && <span className="ac-tag studio-output-progress" role="status">{failed ? t('生成失败') : onDemand ? t('备选片段 · 需要时再生成') : variant.status === 'preparing' ? t('正在准备取景与包装') : job?.status === 'running' ? t('正在生成') : t('排队生成中')}</span>}</div>
    <div className="ac-card-body">
      <h2 className="ac-card-title">{title}</h2>
      {metaLine && <p className="studio-result-meta">{metaLine}</p>}
      {variant.trimmed_to_sec && <p className="studio-output-hint">{t('平台上限 {{seconds}} 秒，已在句子结束处截断', { seconds: variant.trimmed_to_sec })}</p>}
      {packagingHint && <p className="studio-output-hint">{packagingHint}</p>}
      {failed && <p className="studio-output-hint studio-error">{(() => { const step = failureStep('render', null, variant.error_code); const text = readableFailure(variant.error || job?.error, variant.error_code); return step ? `${t(step)}：${t(text)}` : t(text) })()}</p>}
      {failed && billable && <p className="studio-billing">{t(BILLING_GUIDANCE)}</p>}
      <div className="ac-card-foot"><div className={`ac-card-actions${hasEdit ? ' ac-card-actions--with-edit' : ''}`}>
        {completed && variant.render_job_id && <StudioDownloadLink className="studio-output-download" projectId={projectId} jobId={variant.render_job_id} onSaved={downloaded} variant={analytics}/>}
        {completed && variant.render_job_id
          ? <Btn size="sm" onClick={() => navigate(studioPublishPreviewPath(projectId, job.draft_id, job.job_id, variant.id))}>{t('发布')}</Btn>
          : draft && <Btn variant="text" onClick={() => navigate(`/project/${projectId}/studio/${draft.id}?variant=${encodeURIComponent(variant.id)}`)}>{t('预览与修改')}</Btn>}
        {hasEdit && <Btn size="sm" className="studio-card-edit-btn" title={t('编辑')} aria-label={`${t('编辑')} · ${title}`} onClick={() => navigate(`/project/${projectId}/studio/${draft.id}?variant=${encodeURIComponent(variant.id)}&export=${encodeURIComponent(variant.render_job_id!)}`)}><Icon.Edit size={15} /></Btn>}
        {failed && <Btn variant="text" onClick={onRetry}>{t('重试这条')}</Btn>}
        {onDemand && <Btn variant="text" onClick={onProduce}>{t('生成这条')}</Btn>}
      </div></div>
      {asking && <OutputFeedback projectId={projectId} variant={analytics} onDone={() => setAsking(false)}/>}
    </div>
  </article>
}
