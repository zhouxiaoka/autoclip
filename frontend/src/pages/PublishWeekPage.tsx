import { getLocale, t } from '../i18n'
import { useTranslation } from 'react-i18next'
import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { projectApi } from '../services/api'
import { Btn, Icon, ProgressLine, Row, StatusDot } from '../ui'
import {
  defaultPlatforms, planWeek, privateExtra, readApiDetail, remainingClips, renderPreset,
  type WeekClip, type WeekRecord,
} from '../publish/uploadPost'
import { uploadPostApi } from '../publish/uploadPostApi'

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

function shownScore(score: number | undefined): number {
  const value = score || 0
  return value <= 1 ? Math.round(value * 100) : Math.round(value)
}

function slotWhen(date: Date): string {
  return new Intl.DateTimeFormat(getLocale(), {
    weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  }).format(date)
}

const PublishWeekPage: React.FC = () => {
  useTranslation()
  const { id: projectId = '' } = useParams()
  const navigate = useNavigate()
  const runId = useRef(0)
  const [clips, setClips] = useState<WeekClip[]>([])
  const [records, setRecords] = useState<WeekRecord[]>([])
  const [configured, setConfigured] = useState(false)
  const [platforms, setPlatforms] = useState<string[]>([])
  const [user, setUser] = useState('')
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [now] = useState(() => new Date())

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const [cfg, recordRes, loaded] = await Promise.all([
          uploadPostApi.getConfig(),
          uploadPostApi.records(projectId),
          projectApi.getClips(projectId),
        ])
        if (cancelled) return
        setConfigured(cfg.configured)
        setRecords(recordRes.records || [])
        setClips((loaded || []).map((clip) => ({
          id: clip.id,
          title: clip.generated_title || clip.title || '',
          score: clip.final_score || 0,
        })))
        if (!cfg.configured) return
        const res = await uploadPostApi.profiles()
        if (cancelled) return
        const list = res.profiles || []
        const next = list.some((profile) => profile.username === cfg.user) ? cfg.user : (list[0]?.username || cfg.user || '')
        setUser(next)
        const connected = list.find((profile) => profile.username === next)?.connected_platforms || []
        setPlatforms(defaultPlatforms(connected))
      } catch (err) {
        if (!cancelled) setError(readApiDetail(err, t("发布失败")))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
      runId.current += 1
    }
  }, [projectId])

  const slots = useMemo(() => planWeek(clips, records, now), [clips, records, now])
  const fresh = slots.filter((slot) => slot.state === 'new' && slot.clipId)
  const nothingLeft = !remainingClips(clips, records).length

  const confirm = async () => {
    if (!fresh.length || running) return
    if (!platforms.length) {
      setError(t("至少选一个平台"))
      return
    }
    if (!user) {
      setError(t("还没有 profile。到 Upload-Post 创建一个，并连接要发布的账号。"))
      return
    }
    const session = ++runId.current
    setRunning(true)
    setError(null)
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
    try {
      for (let index = 0; index < fresh.length; index += 1) {
        if (runId.current !== session) return
        const slot = fresh[index]
        setProgress({ done: index + 1, total: fresh.length })
        const started = await uploadPostApi.start(projectId, slot.clipId!, {
          platforms,
          user,
          preset: renderPreset(platforms),
          subtitles: true,
          title_card: true,
          scheduled_date: slot.stamp,
          timezone,
          extra: privateExtra(platforms, 'private'),
        })
        if (runId.current !== session) return
        const deadline = Date.now() + 30 * 60 * 1000
        let submitted = false
        while (Date.now() < deadline) {
          if (runId.current !== session) return
          await sleep(2000)
          if (runId.current !== session) return
          const job = await uploadPostApi.job(started.job_id)
          if (runId.current !== session) return
          if (job.status === 'failed') {
            setError(job.error || t("发布失败"))
            setRunning(false)
            return
          }
          if (job.status === 'submitted') {
            submitted = true
            break
          }
        }
        if (!submitted) {
          setError(t("发布失败"))
          setRunning(false)
          return
        }
      }
      if (runId.current !== session) return
      navigate(`/project/${projectId}/publish?view=calendar`)
    } catch (err) {
      if (runId.current !== session) return
      setError(readApiDetail(err, t("发布失败")))
      setRunning(false)
    }
  }

  return (
    <div className="ac-page ac-page--narrow">
      <header>
        <button className="ac-back" onClick={() => navigate(`/project/${projectId}/publish`)}>
          <Icon.Back />{t("发布")}
        </button>
        <h1 className="ac-title">{t("排这一周")}</h1>
      </header>

      {loading && <div style={{ marginTop: 28 }}><StatusDot tone="accent" label={t("还在处理中")} /></div>}
      {!loading && !configured && !error && (
        <div className="ac-empty" style={{ marginTop: 28 }}>
          <b>{t("还没有配置发布密钥。到设置里填一次即可。")}</b>
          <div style={{ marginTop: 14 }}>
            <Btn size="sm" variant="cta" onClick={() => navigate('/settings?section=publish')}>{t("去设置")}</Btn>
          </div>
        </div>
      )}
      {!loading && configured && (
        <>
          <p className="ac-sub" style={{ marginTop: 20 }}>
            {t("按分数把还没发的切片填进每周一、三、五的 09:00。确认之后才会提交，默认仅自己可见。")}
          </p>
          <div className="ac-rows" style={{ marginTop: 8 }}>
            {slots.map((slot) => {
              const title = slot.title || t("切片")
              const hint = slot.state === 'empty'
                ? t("这一档还空着")
                : slot.state === 'taken'
                  ? (slot.title || t("这一档已经有安排"))
                  : `${title} · ${t("分数 {{score}}", { score: shownScore(slot.score) })}`
              return (
                <Row key={slot.stamp} label={<span className="ac-mono">{slotWhen(slot.at)}</span>} hint={hint} />
              )
            })}
          </div>
          {nothingLeft && <p className="ac-sub">{t("这一周没有还没发过的切片。")}</p>}
          <p className="ac-sub">{t("TikTok 每天最多 15 条，YouTube 每天最多 10 条。这一周每天只排一条。")}</p>
          {running && progress && (
            <>
              <div style={{ marginTop: 16 }}><ProgressLine percent={Math.round((progress.done / progress.total) * 100)} /></div>
              <p className="ac-sub">{t("正在排第 {{done}} 条，共 {{total}} 条", progress)}</p>
            </>
          )}
          {!platforms.length && <p className="ac-sub">{t("这个账号还没有连接平台。")}</p>}
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 28 }}>
            <Btn variant="cta" loading={running} disabled={!fresh.length || !platforms.length} onClick={() => void confirm()}>{t("确认排期")}</Btn>
          </div>
        </>
      )}
      {error && <p style={{ marginTop: 12, color: 'var(--ac-error)', fontSize: 13 }}>{error}</p>}
    </div>
  )
}

export default PublishWeekPage
