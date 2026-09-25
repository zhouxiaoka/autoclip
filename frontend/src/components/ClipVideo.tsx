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

  useEffect(() => {
    setFailed(false)
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
  }, [playing, url, failed])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', background: 'var(--ac-thumb)' }}>
      <video
        ref={ref}
        src={url}
        controls
        playsInline
        preload="metadata"
        style={{ width: '100%', height: '100%', display: 'block', objectFit: 'contain', background: 'var(--ac-thumb)' }}
        onPlay={onPlay}
        onPause={onPause}
        onEnded={onEnded}
        onError={() => setFailed(true)}
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
