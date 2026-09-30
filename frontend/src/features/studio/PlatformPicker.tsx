import { useEffect, useState } from 'react'
import { t } from '../../i18n'
import { studioApi } from './api'
import { platformLabel } from './platformLabel'
import type { PlatformStrategySummary } from './types'

const fallback: PlatformStrategySummary[] = [
  { id: 'douyin', label: '抖音', aspect: 'portrait', duration_policy: 'short', min_recommended_duration_sec: 15, max_duration_sec: null, transport: 'download_only', transport_platform: null },
  { id: 'tiktok', label: 'TikTok', aspect: 'portrait', duration_policy: 'short', min_recommended_duration_sec: 15, max_duration_sec: null, transport: 'upload_post', transport_platform: 'tiktok' },
  { id: 'youtube_shorts', label: 'YouTube Shorts', aspect: 'portrait', duration_policy: 'short', min_recommended_duration_sec: 15, max_duration_sec: 180, transport: 'upload_post', transport_platform: 'youtube' },
  { id: 'youtube_long', label: 'YouTube 视频', aspect: 'landscape', duration_policy: 'long', min_recommended_duration_sec: 180, max_duration_sec: null, transport: 'upload_post', transport_platform: 'youtube' },
  { id: 'bilibili', label: 'B站', aspect: 'landscape', duration_policy: 'adaptive', min_recommended_duration_sec: 180, max_duration_sec: null, transport: 'bilibili_direct', transport_platform: 'bilibili' },
  { id: 'xiaohongshu', label: '小红书', aspect: 'portrait', duration_policy: 'short', min_recommended_duration_sec: 20, max_duration_sec: null, transport: 'download_only', transport_platform: null },
]

function summary(strategy: PlatformStrategySummary): string {
  if (strategy.duration_policy === 'long') return t('完整横版内容')
  if (strategy.duration_policy === 'short') return t('短视频')
  return t('自适应成片')
}

export default function PlatformPicker({ value, onChange, disabled = false }: { value: string[]; onChange: (next: string[]) => void; disabled?: boolean }) {
  const [strategies, setStrategies] = useState<PlatformStrategySummary[]>(fallback)
  useEffect(() => {
    let active = true
    void studioApi.platformStrategies().then(data => { if (active && data.strategies.length) setStrategies(data.strategies) }).catch(() => undefined)
    return () => { active = false }
  }, [])
  const toggle = (id: string) => {
    if (disabled) return
    const selected = value.includes(id)
    const next = selected ? value.filter(item => item !== id) : [...value, id]
    onChange(next.length ? next : [id])
  }
  return <fieldset className="studio-platform-picker" disabled={disabled}>
    <legend>{t('准备发布到哪里？')}</legend>
    <p className="studio-muted">{t('默认选一个平台；多选时会复用同一次内容分析。')}</p>
    <div className="studio-platform-options">
      {strategies.filter(strategy => strategy.id !== 'original').map(strategy => {
        const selected = value.includes(strategy.id)
        return <button type="button" key={strategy.id} className={`studio-platform-option${selected ? ' is-selected' : ''}`} aria-pressed={selected} onClick={() => toggle(strategy.id)}>
          <b>{platformLabel(strategy.id)}</b><span>{summary(strategy)}</span>
        </button>
      })}
    </div>
  </fieldset>
}
