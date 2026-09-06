import React, { useState, useEffect, useRef } from 'react'
import { Modal, message } from 'antd'
import ReactPlayer from 'react-player'
import { Clip } from '../store/useProjectStore'
import BilibiliManager from './BilibiliManager'
import EditableTitle from './EditableTitle'
import { Btn, Icon, parseTimecode, fmtDuration, fmtClock } from '../ui'

interface ClipCardProps {
  clip: Clip
  videoUrl?: string
  onDownload: (clipId: string) => void
  projectId?: string
  onClipUpdate?: (clipId: string, updates: Partial<Clip>) => void
}

// Calm Premium clip card — see DESIGN.md → App Layer / Media card
const ClipCard: React.FC<ClipCardProps> = ({ clip, videoUrl, onDownload, projectId, onClipUpdate }) => {
  const [showPlayer, setShowPlayer] = useState(false)
  const [videoThumbnail, setVideoThumbnail] = useState<string | null>(null)
  const [showBilibiliManager, setShowBilibiliManager] = useState(false)
  const playerRef = useRef<ReactPlayer>(null)

  // 从视频第 1 秒抓一帧当缩略图
  useEffect(() => {
    if (!videoUrl) return
    const video = document.createElement('video')
    video.crossOrigin = 'anonymous'
    video.currentTime = 1
    video.onloadeddata = () => {
      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      ctx.drawImage(video, 0, 0)
      setVideoThumbnail(canvas.toDataURL('image/jpeg', 0.8))
    }
    video.src = videoUrl
  }, [videoUrl])

  const handleDownload = async () => {
    try {
      await onDownload(clip.id)
    } catch (err) {
      console.error('下载失败:', err)
      message.error('下载失败')
    }
  }

  const durationSec = Math.max(0, parseTimecode(clip.end_time) - parseTimecode(clip.start_time))

  // 优先显示推荐理由；否则取内容要点；最后回退到大纲
  const getDisplayContent = () => {
    if (clip.recommend_reason && clip.recommend_reason.trim()) return clip.recommend_reason
    if (clip.content && Array.isArray(clip.content) && clip.content.length > 0) {
      const points = clip.content.filter((item) => {
        const text = item.trim()
        if (text.length > 100) return false
        if (text.split(/[，。！？；：""''（）【】]/).length > 3) return false
        return true
      })
      if (points.length > 0) return points.join(' ')
    }
    if (clip.outline && clip.outline.trim()) return clip.outline
    return ''
  }

  const title = clip.title || clip.generated_title || '未命名片段'
  // 后端评分历史上有 0–1 / 0–10 两种刻度，统一显示为 0–100 的整数
  const raw = clip.final_score ?? 0
  const score = Math.round(raw <= 1 ? raw * 100 : raw <= 10 ? raw * 10 : raw)

  return (
    <>
      <article className="ac-card">
        <div
          className="ac-card-thumb"
          style={videoThumbnail ? { backgroundImage: `url(${videoThumbnail})` } : undefined}
          onClick={() => setShowPlayer(true)}
          role="button"
          aria-label="播放"
        >
          <div className="play"><span><Icon.Play size={18} /></span></div>
          <span className="ac-tag ac-tag--tr" title="推荐分">{score}</span>
          <span className="ac-tag ac-tag--bl">{fmtClock(clip.start_time)} – {fmtClock(clip.end_time)}</span>
        </div>

        <div className="ac-card-body">
          <div className="ac-card-title">
            <EditableTitle
              title={title}
              clipId={clip.id}
              onTitleUpdate={(t) => onClipUpdate?.(clip.id, { title: t })}
              style={{ fontSize: 'inherit', fontWeight: 'inherit', lineHeight: 'inherit', color: 'inherit', width: '100%' }}
            />
          </div>
          <div className="ac-card-desc" title={getDisplayContent()}>{getDisplayContent()}</div>
          <div className="ac-card-foot">
            <span className="meta">{fmtDuration(durationSec)}</span>
            <div className="ac-card-actions">
              <Btn variant="text" onClick={() => setShowPlayer(true)}>播放</Btn>
              <Btn variant="text" onClick={handleDownload}>下载</Btn>
              <Btn variant="text" onClick={() => message.info('投稿功能开发中', 3)}>投稿</Btn>
            </div>
          </div>
        </div>
      </article>

      <Modal
        open={showPlayer}
        onCancel={() => setShowPlayer(false)}
        footer={
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <Btn size="sm" onClick={() => message.info('投稿功能开发中', 3)}>投稿到 B 站</Btn>
            <Btn size="sm" variant="cta" onClick={handleDownload} style={{ height: 30, fontSize: 12.5, padding: '0 14px' }}>
              下载
            </Btn>
          </div>
        }
        width={820}
        centered
        destroyOnClose
        closeIcon={<span style={{ color: 'var(--ac-sub)', fontSize: 16 }}>×</span>}
        title={
          <div style={{ paddingRight: 30 }}>
            <EditableTitle
              title={clip.title || clip.generated_title || '视频预览'}
              clipId={clip.id}
              onTitleUpdate={(t) => onClipUpdate?.(clip.id, { title: t })}
              style={{ color: 'var(--ac-ink)', fontSize: 15, fontWeight: 500 }}
            />
            <div className="ac-meta" style={{ marginTop: 4 }}>
              <span className="ac-mono">{fmtClock(clip.start_time)} – {fmtClock(clip.end_time)}</span>
              <span className="dot" />
              <span className="ac-mono">{fmtDuration(durationSec)}</span>
              <span className="dot" />
              <span>推荐分 <span className="ac-mono">{score}</span></span>
            </div>
          </div>
        }
      >
        {videoUrl && (
          <div style={{ borderRadius: 12, overflow: 'hidden', background: '#000' }}>
            <ReactPlayer
              ref={playerRef}
              url={videoUrl}
              width="100%"
              height="430px"
              controls
              playing={showPlayer}
              config={{ file: { attributes: { controlsList: 'nodownload', preload: 'metadata' }, forceHLS: false, forceDASH: false } }}
              onError={(err) => console.error('ReactPlayer error:', err)}
            />
          </div>
        )}
      </Modal>

      <BilibiliManager
        visible={showBilibiliManager}
        onClose={() => setShowBilibiliManager(false)}
        projectId={projectId || ''}
        clipIds={[clip.id]}
        clipTitles={[title]}
        onUploadSuccess={() => console.log('投稿成功')}
      />
    </>
  )
}

export default ClipCard
