import React, { useState, useEffect, useRef } from 'react'
import { Modal, message } from 'antd'
import ReactPlayer from 'react-player'
import { Clip } from '../store/useProjectStore'
import BilibiliManager from './BilibiliManager'
import EditableTitle from './EditableTitle'
import { projectApi } from '../services/api'
import { Btn, Dialog, Icon, ProgressLine, Row, Segmented, parseTimecode, fmtDuration, fmtClock } from '../ui'

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
  const [showExport, setShowExport] = useState(false)
  const [preset, setPreset] = useState<'douyin' | 'xiaohongshu' | 'shorts' | 'bilibili' | 'original'>('douyin')
  const [burnSub, setBurnSub] = useState(true)
  const [titleCard, setTitleCard] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [exportPercent, setExportPercent] = useState(0)
  const [exportError, setExportError] = useState<string | null>(null)
  const [exportDone, setExportDone] = useState<{ jobId: string; warnings?: string[] } | null>(null)
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

  const handleExport = async () => {
    if (!projectId) return
    setExporting(true)
    setExportError(null)
    setExportDone(null)
    setExportPercent(5)
    try {
      const started = await projectApi.startClipExport(projectId, clip.id, {
        preset, subtitles: burnSub, title_card: titleCard,
      })
      const jobId = started.job_id
      for (let i = 0; i < 180; i++) {
        await new Promise((r) => setTimeout(r, 1000))
        const job = await projectApi.getExportJob(projectId, jobId)
        setExportPercent(job.percent ?? 10)
        if (job.status === 'completed') {
          setExportDone({ jobId, warnings: job.result?.warnings })
          setExporting(false)
          return
        }
        if (job.status === 'failed') {
          setExportError(job.error || '导出失败')
          setExporting(false)
          return
        }
      }
      setExportError('导出超时，请稍后在输出目录查看')
    } catch (err: any) {
      setExportError(err?.response?.data?.detail || err?.message || '导出失败')
    } finally {
      setExporting(false)
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
              {projectId && <Btn variant="text" onClick={() => { setShowExport(true); setExportDone(null); setExportError(null) }}>导出</Btn>}
            </div>
          </div>
        </div>
      </article>

      <Modal
        open={showPlayer}
        onCancel={() => setShowPlayer(false)}
        footer={
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            {projectId && <Btn size="sm" onClick={() => { setShowPlayer(false); setShowExport(true) }}>发布导出</Btn>}
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

      <Dialog
        open={showExport}
        onClose={() => !exporting && setShowExport(false)}
        title="发布导出"
        description="渲成可直接上传的成片。默认流水线的切片不受影响。"
        footer={
          <div className="right" style={{ marginLeft: 'auto' }}>
            <Btn size="sm" onClick={() => setShowExport(false)} disabled={exporting}>取消</Btn>
            {exportDone ? (
              <Btn size="sm" variant="cta" onClick={() => projectId && projectApi.downloadExport(projectId, exportDone.jobId)}>
                下载成片
              </Btn>
            ) : (
              <Btn size="sm" variant="cta" loading={exporting} onClick={handleExport}>开始导出</Btn>
            )}
          </div>
        }
      >
        <Row label="平台" hint="画幅与时长按平台规格">
          <Segmented
            size="sm"
            ariaLabel="导出预设"
            value={preset}
            onChange={setPreset}
            options={[
              { value: 'douyin', label: '抖音' },
              { value: 'xiaohongshu', label: '小红书' },
              { value: 'shorts', label: 'Shorts' },
              { value: 'bilibili', label: 'B 站' },
              { value: 'original', label: '原画' },
            ]}
          />
        </Row>
        <Row label="字幕" hint="从原字幕切出本段并烧进画面">
          <Segmented size="sm" value={burnSub ? 'on' : 'off'} onChange={(v) => setBurnSub(v === 'on')}
            options={[{ value: 'on', label: '烧录' }, { value: 'off', label: '不要' }]} />
        </Row>
        <Row label="标题卡" hint="片头约 4 秒显示切片标题">
          <Segmented size="sm" value={titleCard ? 'on' : 'off'} onChange={(v) => setTitleCard(v === 'on')}
            options={[{ value: 'on', label: '显示' }, { value: 'off', label: '不要' }]} />
        </Row>
        {exporting && <div style={{ marginTop: 16 }}><ProgressLine percent={exportPercent} /></div>}
        {exportError && <p style={{ marginTop: 12, color: 'var(--ac-error)', fontSize: 13 }}>{exportError}</p>}
        {exportDone && (
          <p style={{ marginTop: 12, color: 'var(--ac-sub)', fontSize: 13 }}>
            已完成{exportDone.warnings?.length ? ` · ${exportDone.warnings.join('；')}` : ''}
          </p>
        )}
      </Dialog>

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
