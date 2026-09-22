import { t } from '../i18n'
import { useTranslation } from 'react-i18next'
import React, { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { projectApi } from '../services/api'
import { Btn, Icon, ProgressLine, Row, Segmented, StatusDot } from '../ui'
import { openExternalLink } from '../utils/externalLinks'
import {
  buildSchedule, defaultPlatforms, platformLabel, privateExtra, readApiDetail, renderPreset,
  type PublishVisibility,
} from '../publish/uploadPost'
import { uploadPostApi, type PlatformResult, type UploadPostProfile } from '../publish/uploadPostApi'

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

function defaultWhen(): string {
  const date = new Date()
  date.setDate(date.getDate() + 1)
  date.setHours(9, 0, 0, 0)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const PublishClipPage: React.FC = () => {
  useTranslation()
  const { id: projectId = '', clipId = '' } = useParams()
  const navigate = useNavigate()
  const runId = useRef(0)

  const [clipTitle, setClipTitle] = useState('')
  const [loading, setLoading] = useState(true)
  const [configured, setConfigured] = useState(false)
  const [profiles, setProfiles] = useState<UploadPostProfile[]>([])
  const [user, setUser] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [visibility, setVisibility] = useState<PublishVisibility>('private')
  const [when, setWhen] = useState<'now' | 'later'>('now')
  const [whenValue, setWhenValue] = useState(defaultWhen)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [subtitles, setSubtitles] = useState(true)
  const [titleCard, setTitleCard] = useState(true)
  const [savingFile, setSavingFile] = useState(false)
  const [phase, setPhase] = useState<'idle' | 'running' | 'waiting' | 'done' | 'partial' | 'failed' | 'scheduled'>('idle')
  const [percent, setPercent] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<PlatformResult[]>([])

  useEffect(() => {
    const session = ++runId.current
    let cancelled = false
    const load = async () => {
      setLoading(true)
      try {
        const [project, cfg] = await Promise.all([
          projectApi.getProject(projectId),
          uploadPostApi.getConfig(),
        ])
        if (cancelled || runId.current !== session) return
        let clips = project.clips || []
        if (!clips.length) {
          try { clips = await projectApi.getClips(projectId) } catch { clips = [] }
        }
        const clip = clips.find((item) => item.id === clipId)
        setClipTitle(clip?.generated_title || clip?.title || '')
        setConfigured(cfg.configured)
        if (!cfg.configured) return
        const res = await uploadPostApi.profiles()
        if (cancelled || runId.current !== session) return
        const list = res.profiles || []
        setProfiles(list)
        const next = list.some((p) => p.username === cfg.user) ? cfg.user : (list[0]?.username || cfg.user || '')
        setUser(next)
        const connected = list.find((p) => p.username === next)?.connected_platforms || []
        setSelected(defaultPlatforms(connected))
      } catch (err) {
        if (!cancelled && runId.current === session) setError(readApiDetail(err, t("发布失败")))
      } finally {
        if (!cancelled && runId.current === session) setLoading(false)
      }
    }
    void load()
    return () => { cancelled = true }
  }, [projectId, clipId])

  const chooseUser = (next: string) => {
    setUser(next)
    const connected = profiles.find((p) => p.username === next)?.connected_platforms || []
    setSelected(defaultPlatforms(connected))
  }

  const toggle = (platform: string) => {
    setSelected((cur) => cur.includes(platform) ? cur.filter((p) => p !== platform) : [...cur, platform])
  }

  const profile = profiles.find((p) => p.username === user)
  const connected = profile?.connected_platforms || []
  const reconnect = (profile?.reconnect_platforms || []).map(platformLabel).join(' · ')
  const busy = phase === 'running' || phase === 'waiting' || savingFile
  const preset = renderPreset(selected)
  const longYoutube = selected.includes('youtube') && title.trim().length > 100

  const publish = async () => {
    if (!selected.length) {
      setError(t("至少选一个平台"))
      return
    }
    if (!user) {
      setError(t("还没有 profile。到 Upload-Post 创建一个，并连接要发布的账号。"))
      return
    }
    const schedule = buildSchedule(when, whenValue, Intl.DateTimeFormat().resolvedOptions().timeZone, Date.now())
    if (!schedule.ok) {
      setError(schedule.reason === 'empty' ? t("选择发出的时间") : t("时间要晚于现在"))
      return
    }
    const session = runId.current
    const later = when === 'later'
    setError(null)
    setResults([])
    setPhase('running')
    setPercent(12)
    try {
      const started = await uploadPostApi.start(projectId, clipId, {
        platforms: selected,
        user,
        preset,
        title: title.trim() || undefined,
        description: description.trim() || undefined,
        subtitles,
        title_card: titleCard,
        scheduled_date: schedule.scheduled_date,
        timezone: schedule.timezone,
        extra: privateExtra(selected, visibility),
      })
      if (runId.current !== session) return
      const deadline = Date.now() + 30 * 60 * 1000
      let waitMs = 2000
      let submitted = false
      while (Date.now() < deadline) {
        if (runId.current !== session) return
        await sleep(waitMs)
        if (runId.current !== session) return
        const job = await uploadPostApi.job(started.job_id)
        if (runId.current !== session) return
        if (job.status === 'failed') {
          setError(job.error || t("发布失败"))
          setPhase('failed')
          setPercent(100)
          return
        }
        if (job.status === 'submitted') {
          submitted = true
          if (later) {
            setPhase('scheduled')
            setPercent(100)
            return
          }
          waitMs = 10000
          setPhase('waiting')
          setPercent(72)
          const remote = job.remote
          if (remote?.results) setResults(remote.results)
          if (remote?.final) {
            const bad = (remote.results || []).some((r) => !r.success && !r.skipped)
            setPhase(bad ? 'partial' : 'done')
            setPercent(100)
            return
          }
        } else {
          waitMs = 2000
          setPhase('running')
          setPercent(36)
        }
      }
      setPhase(submitted ? 'waiting' : 'running')
      setError(submitted ? t("已提交，正在等各平台结果") : t("正在渲成片并提交"))
    } catch (err) {
      setError(readApiDetail(err, t("发布失败")))
      setPhase('failed')
    }
  }

  const downloadFile = async () => {
    if (savingFile || phase === 'running' || phase === 'waiting') return
    setSavingFile(true)
    setError(null)
    setPercent(8)
    try {
      const started = await projectApi.startClipExport(projectId, clipId, {
        preset,
        subtitles,
        title_card: titleCard,
      })
      for (let i = 0; i < 180; i++) {
        await sleep(1000)
        const job = await projectApi.getExportJob(projectId, started.job_id)
        setPercent(job.percent ?? 20)
        if (job.status === 'completed') {
          await projectApi.downloadExport(projectId, started.job_id)
          setPercent(100)
          return
        }
        if (job.status === 'failed') {
          setError(job.error || t("导出失败"))
          return
        }
      }
      setError(t("导出超时，请稍后在输出目录查看"))
    } catch (err) {
      setError(readApiDetail(err, t("导出失败")))
    } finally {
      setSavingFile(false)
    }
  }

  const summary = phase === 'done'
    ? t("各平台都已完成")
    : phase === 'partial'
      ? t("有的平台没有发出去")
      : phase === 'scheduled'
        ? t("已排期。到点会自动发出，可以关掉应用。")
        : phase === 'waiting'
          ? t("已提交，正在等各平台结果")
          : phase === 'running'
            ? t("正在渲成片并提交")
            : null

  return (
    <div className="ac-page ac-page--narrow">
      <header>
        <button className="ac-back" onClick={() => navigate(`/project/${projectId}`)}>
          <Icon.Back />{t("项目")}
        </button>
        <h1 className="ac-title">{t("发布")}</h1>
        <div className="ac-meta">
          <span>{clipTitle || t("切片")}</span>
        </div>
      </header>

      <div className="ac-rows" style={{ marginTop: 28 }}>
        {loading && <div style={{ padding: '28px 0' }}><StatusDot tone="accent" label={t("还在处理中")} /></div>}
        {!loading && !configured && !error && (
          <div className="ac-empty" style={{ marginTop: 8 }}>
            <b>{t("还没有配置发布密钥。到设置里填一次即可。")}</b>
            <div style={{ marginTop: 14 }}>
              <Btn size="sm" variant="cta" onClick={() => navigate('/settings?section=publish')}>{t("去设置")}</Btn>
            </div>
          </div>
        )}
        {!loading && configured && (
          <>
            {profiles.length > 1 && (
              <Row label={t("默认账号")}>
                <Segmented size="sm" ariaLabel={t("默认账号")} value={user} onChange={chooseUser}
                  options={profiles.map((p) => ({ value: p.username, label: p.username }))} />
              </Row>
            )}
            <Row label={t("何时")}>
              <Segmented size="sm" ariaLabel={t("何时")} value={when} onChange={setWhen}
                options={[{ value: 'now', label: t("现在发") }, { value: 'later', label: t("定时") }]} />
            </Row>
            {when === 'later' && (
              <Row label={t("选择发出的时间")}>
                <input className="ac-input" style={{ width: 220 }} type="datetime-local" aria-label={t("选择发出的时间")} value={whenValue} onChange={(e) => setWhenValue(e.target.value)} />
              </Row>
            )}
            {connected.length > 0 && (
              <Row label={t("选择要发布的平台")} stack>
                <div className="ac-seg ac-seg--sm" role="group" aria-label={t("选择要发布的平台")}>
                  {connected.map((p) => (
                    <button key={p} type="button" aria-pressed={selected.includes(p)} onClick={() => toggle(p)} disabled={busy}>{platformLabel(p)}</button>
                  ))}
                </div>
              </Row>
            )}
            {profiles.length > 0 && !connected.length && !reconnect && (
              <p style={{ color: 'var(--ac-sub)', fontSize: 13 }}>{t("这个账号还没有连接平台。")}</p>
            )}
            {reconnect && (
              <p style={{ color: 'var(--ac-sub)', fontSize: 13, margin: '8px 0 0' }}>{t("需要重新连接：{{platforms}}", { platforms: reconnect })}</p>
            )}
            <Row label={t("可见范围")} hint={t("默认先发到自己看得到的地方。公开会直接出现在账号上。")}>
              <Segmented size="sm" ariaLabel={t("可见范围")} value={visibility} onChange={setVisibility}
                options={[{ value: 'private', label: t("仅自己") }, { value: 'public', label: t("公开") }]} />
            </Row>
            <Row wide label={t("标题")} hint={longYoutube ? t("YouTube 标题超过 100 字时会自动缩短。") : t("不填就用切片标题。")}>
              <input className="ac-input" aria-label={t("标题")} value={title} onChange={(e) => setTitle(e.target.value)} />
            </Row>
            <Row wide label={t("描述")} hint={t("只有 YouTube、LinkedIn、Facebook、Pinterest 会用到。")}>
              <textarea className="ac-input ac-textarea" style={{ minHeight: 88 }} aria-label={t("描述")} value={description} onChange={(e) => setDescription(e.target.value)} />
            </Row>
          </>
        )}
        {!loading && (
          <>
            <Row label={t("字幕")} hint={t("从原字幕切出本段并烧进画面")}>
              <Segmented size="sm" ariaLabel={t("字幕")} value={subtitles ? 'on' : 'off'} onChange={(v) => setSubtitles(v === 'on')}
                options={[{ value: 'on', label: t("烧录") }, { value: 'off', label: t("不要") }]} />
            </Row>
            <Row label={t("标题卡")} hint={t("片头约 4 秒显示切片标题")}>
              <Segmented size="sm" ariaLabel={t("标题卡")} value={titleCard ? 'on' : 'off'} onChange={(v) => setTitleCard(v === 'on')}
                options={[{ value: 'on', label: t("显示") }, { value: 'off', label: t("不要") }]} />
            </Row>
          </>
        )}
      </div>

      {!loading && (
        <p className="ac-sub" style={{ marginTop: 16 }}>
          {t("成片跟着账号走：有竖屏账号就渲成 9:16，只有横屏账号时按原画。")}
        </p>
      )}
      {busy && <div style={{ marginTop: 16 }}><ProgressLine percent={percent} /></div>}
      {summary && <p style={{ marginTop: 12, color: 'var(--ac-sub)', fontSize: 13 }}>{summary}</p>}
      {results.length > 0 && (
        <div style={{ marginTop: 8 }}>
          {results.map((r) => {
            const tone = r.skipped ? 'muted' : r.success ? 'ok' : 'error'
            const note = r.skipped
              ? t("该平台未连接，已跳过")
              : r.fallback_to_inbox
                ? t("进了 TikTok 收件箱，需要在 App 里再发一次")
                : (r.error || r.message || '')
            return (
              <div key={r.platform} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', padding: '10px 0', borderTop: '1px solid var(--ac-line)' }}>
                <StatusDot tone={tone} label={<>{platformLabel(r.platform || '')}{note ? <span style={{ color: 'var(--ac-muted)' }}> · {note}</span> : null}</>} />
                {r.url && (
                  <a href={r.url} onClick={(e) => { e.preventDefault(); void openExternalLink(r.url!) }} style={{ color: 'var(--ac-accent)', fontSize: 13 }}>{t("打开链接")}</a>
                )}
              </div>
            )
          })}
        </div>
      )}
      {error && <p style={{ marginTop: 12, color: 'var(--ac-error)', fontSize: 13 }}>{error}</p>}

      {!loading && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 28 }}>
          <Btn loading={savingFile} disabled={phase === 'running' || phase === 'waiting'} onClick={() => void downloadFile()}>{t("下载成片")}</Btn>
          {configured && phase !== 'done' && phase !== 'partial' && phase !== 'scheduled' && (
            <Btn variant="cta" loading={phase === 'running' || phase === 'waiting'} disabled={!selected.length || savingFile} onClick={() => void publish()}>
              {when === 'later' ? t("排期发布") : t("开始发布")}
            </Btn>
          )}
          {(phase === 'done' || phase === 'partial' || phase === 'scheduled') && (
            <Btn onClick={() => navigate(`/project/${projectId}/publish`)}>{t("查看发布记录")}</Btn>
          )}
        </div>
      )}
    </div>
  )
}

export default PublishClipPage
