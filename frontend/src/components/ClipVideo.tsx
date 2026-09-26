import { authorizeMediaUrl, isDesktop } from '../utils/auth'
import { useEffect, useRef, useState } from 'react'
import { t } from '../i18n'

type ClipVideoProps = {
  url: string
  playing?: boolean
  onPlay?: () => void
  onPause?: () => void
  onEnded?: () => void
}

/**
 * In-app clip preview.
 *
 * react-player 2.13 only mounts a <video> when the URL ends in a media
 * extension (see VIDEO_EXTENSIONS). Clip URLs are
 * `/api/v1/projects/:id/clips/:clipId` with no extension, so ReactPlayer
 * renders nothing inside the black player well. A native <video> follows
 * Content-Type instead.
 */
export default function ClipVideo({ url, playing = false, onPlay, onPause, onEnded }: ClipVideoProps) {
  const ref = useRef<HTMLVideoElement>(null)
  const [failed, setFailed] = useState(false)
  const [source, setSource] = useState<string>()
  const issuedAt = useRef(0)
  const resume = useRef<{ time: number; playing: boolean }>()
  const refresh = () => {
    if (!isDesktop() || Date.now() - issuedAt.current < 45000) return false
    issuedAt.current = Date.now()
    const el = ref.current
    resume.current = { time: el?.currentTime || 0, playing: el ? !el.paused : playing }
    void authorizeMediaUrl(url).then(value => setSource(value)).catch(() => setFailed(true))
    return true
  }

  useEffect(() => {
    let cancelled = false
    setFailed(false)
    setSource(undefined)
    void authorizeMediaUrl(url).then(value => { if (!cancelled) { issuedAt.current = Date.now(); setSource(value) } }).catch(() => { if (!cancelled) setFailed(true) })
    return () => { cancelled = true }
  }, [url])

  useEffect(() => {
    const el = ref.current
    if (!el || failed) return
    if (playing) {
      const attempt = el.play()
      if (attempt) attempt.catch(() => { /* controls stay usable if autoplay is blocked */ })
    } else {
      el.pause()
    }
  }, [playing, source, failed])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', background: 'var(--ac-thumb)' }}>
      <video
        ref={ref}
        src={source}
        controls
        playsInline
        preload="metadata"
        style={{ width: '100%', height: '100%', display: 'block', objectFit: 'contain', background: 'var(--ac-thumb)' }}
        onPlay={() => { refresh(); onPlay?.() }}
        onSeeking={() => { refresh() }}
        onLoadedMetadata={() => {
          if (resume.current && ref.current) {
            const previous = resume.current
            resume.current = undefined
            ref.current.currentTime = previous.time
            if (previous.playing) void ref.current.play().catch(() => {})
          }
        }}
        onPause={onPause}
        onEnded={onEnded}
        onError={() => { if (!refresh()) setFailed(true) }}
      />
      {failed && (
        <div
          role="alert"
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 24,
            textAlign: 'center',
            color: 'var(--ac-sub)',
            background: 'var(--ac-thumb)',
          }}
        >
          {t("这个切片当前播放器无法解码，请下载后用系统播放器打开。")}
        </div>
      )}
    </div>
  )
}
