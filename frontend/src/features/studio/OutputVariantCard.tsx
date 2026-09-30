import { useNavigate } from 'react-router-dom'
import { t } from '../../i18n'
import { Btn, fmtDuration } from '../../ui'
import StudioDownloadLink from './StudioDownloadLink'
import { Draft, OutputVariant, RenderJob } from './types'
import './quick-output.css'

const platformLabels: Record<string, string> = {
  douyin: '抖音', tiktok: 'TikTok', instagram_reels: 'Instagram Reels', youtube_shorts: 'YouTube Shorts',
  youtube_long: 'YouTube 视频', bilibili: 'B站', xiaohongshu: '小红书', original: '原画',
}

export default function OutputVariantCard({ projectId, variant, draft, job, onRetry }: { projectId: string; variant: OutputVariant; draft?: Draft; job?: RenderJob; onRetry: () => void }) {
  const navigate = useNavigate()
  const completed = variant.status === 'completed' && job?.status === 'completed'
  const failed = variant.status === 'failed'
  const duration = job?.result?.duration ?? (draft ? draft.scenes.reduce((sum, scene) => sum + scene.end - scene.start, 0) : 0)
  return <article className="ac-card">
    <div className="studio-variant-thumb"><span className="play">▷</span><span className="ac-tag ac-tag--tl">{platformLabels[variant.strategy_id] || variant.strategy_id}</span>{duration > 0 && <span className="ac-tag ac-tag--br">{fmtDuration(duration)}</span>}</div>
    <div className="ac-card-body">
      <h2 className="ac-card-title">{draft?.title || t('正在准备成片')}</h2>
      <div className={`studio-output-state studio-output-state--${failed ? 'failed' : completed ? 'ready' : 'rendering'}`} role="status">
        {completed ? t('已生成 · 可下载') : failed ? t('生成失败') : job?.status === 'queued' ? t('排队生成中') : t('正在生成')}
      </div>
      <p className="studio-output-hint">{variant.branding.outro_enabled ? t('包含 Made with AutoClip 片尾') : t('不含品牌片尾')}</p>
      {failed && <p className="studio-output-hint studio-error">{variant.error || job?.error || t('这条版本未完成，其他成片不受影响。')}</p>}
      <div className="ac-card-foot"><span className="meta">{platformLabels[variant.strategy_id] || variant.strategy_id}</span><div className="ac-card-actions">
        {draft && <Btn variant="text" onClick={() => navigate(`/project/${projectId}/studio/${draft.id}`)}>{t('预览与修改')}</Btn>}
        {failed && <Btn variant="text" onClick={onRetry}>{t('重试这条')}</Btn>}
        {completed && variant.render_job_id && <StudioDownloadLink className="studio-link" projectId={projectId} jobId={variant.render_job_id}/>}
      </div></div>
    </div>
  </article>
}
