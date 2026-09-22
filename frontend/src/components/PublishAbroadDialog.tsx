import { t } from '../i18n'
import { useTranslation } from 'react-i18next'
import React, { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Btn, Dialog, ProgressLine, Row, Segmented, StatusDot } from '../ui'
import { openExternalLink } from '../utils/externalLinks'
import {
  defaultPlatforms, platformLabel, privateExtra, readApiDetail,
  type PublishVisibility,
} from '../publish/uploadPost'
import { uploadPostApi, type PlatformResult, type UploadPostProfile } from '../publish/uploadPostApi'

const PRESET_LABEL: Record<string, string> = {
  douyin: '抖音',
  xiaohongshu: '小红书',
  shorts: 'Shorts',
  bilibili: 'B 站',
  original: '原画',
}

interface Props {
  open: boolean
  onClose: () => void
  projectId: string
  clipId: string
  preset: string
  subtitles: boolean
  titleCard: boolean
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

const PublishAbroadDialog: React.FC<Props> = ({
  open, onClose, projectId, clipId, preset, subtitles, titleCard,
}) => {
  useTranslation()
  const navigate = useNavigate()
  const runId = useRef(0)
  const [loading, setLoading] = useState(false)
  const [configured, setConfigured] = useState(false)
  const [profiles, setProfiles] = useState<UploadPostProfile[]>([])
  const [user, setUser] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [visibility, setVisibility] = useState<PublishVisibility>('private')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [phase, setPhase] = useState<'idle' | 'running' | 'waiting' | 'done' | 'partial' | 'failed'>('idle')
  const [percent, setPercent] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<PlatformResult[]>([])

  useEffect(() => {
    if (!open) {
      runId.current += 1
      return
    }
    const session = runId.current
    setPhase('idle')
    setPercent(0)
    setError(null)
    setResults([])
    setTitle('')
    setDescription('')
    setVisibility('private')
    let cancelled = false
    const load = async () => {
      setLoading(true)
      try {
        const cfg = await uploadPostApi.getConfig()
        if (cancelled || runId.current !== session) return
        setConfigured(cfg.configured)
        if (!cfg.configured) {
          setProfiles([])
          return
        }
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
  }, [open])

  const chooseUser = (next: string) => {
    setUser(next)
    const connected = profiles.find((p) => p.username === next)?.connected_platforms || []
    setSelected(defaultPlatforms(connected))
  }

  const toggle = (platform: string) => {
    setSelected((cur) => cur.includes(platform) ? cur.filter((p) => p !== platform) : [...cur, platform])
  }

  const connected = profiles.find((p) => p.username === user)?.connected_platforms || []
  const busy = phase === 'running' || phase === 'waiting'
  const presetName = PRESET_LABEL[preset] ? t(PRESET_LABEL[preset]) : preset

  const publish = async () => {
    if (!selected.length) {
      setError(t("至少选一个平台"))
      return
    }
    if (!user) {
      setError(t("还没有 profile。到 Upload-Post 创建一个，并连接要发布的账号。"))
      return
    }
    const session = runId.current
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
        extra: privateExtra(selected, visibility),
      })
      if (runId.current !== session) return
      for (let i = 0; i < 150; i++) {
        if (runId.current !== session) return
        await sleep(i < 8 ? 1000 : 4000)
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
          setPhase('running')
          setPercent(36)
        }
      }
      setPhase('waiting')
      setError(t("已提交，正在等各平台结果"))
    } catch (err) {
      setError(readApiDetail(err, t("发布失败")))
      setPhase('failed')
    }
  }

  const goSettings = () => {
    onClose()
    navigate('/settings?section=publish')
  }

  const summary = phase === 'done'
    ? t("各平台都已完成")
    : phase === 'partial'
      ? t("有的平台没有发出去")
      : phase === 'waiting'
        ? t("已提交，正在等各平台结果")
        : phase === 'running'
          ? t("正在渲成片并提交")
          : null

  return (
    <Dialog
      open={open}
      onClose={() => { if (!busy) onClose() }}
      title={t("发到海外平台")}
      description={t("先在本机渲成片，再交给 Upload-Post 发到勾选的平台。与 B 站投稿互不影响。")}
      footer={
        <div className="right" style={{ marginLeft: 'auto' }}>
          <Btn size="sm" onClick={onClose} disabled={busy}>{busy ? t("取消") : (phase === 'idle' ? t("取消") : t("关闭"))}</Btn>
          {phase !== 'done' && phase !== 'partial' && (
            <Btn size="sm" variant="cta" loading={busy} disabled={loading || !configured || !selected.length} onClick={() => void publish()}>{t("开始发布")}</Btn>
          )}
        </div>
      }
    >
      {loading && <StatusDot tone="accent" label={t("还在处理中")} />}
      {!loading && !configured && !error && (
        <div className="ac-empty">
          <b>{t("还没有配置发布密钥。到设置里填一次即可。")}</b>
          <div style={{ marginTop: 14 }}>
            <Btn size="sm" variant="cta" onClick={goSettings}>{t("去设置")}</Btn>
          </div>
        </div>
      )}
      {!loading && configured && (
        <>
          {profiles.length > 1 && (
            <Row label={t("默认账号")} stack>
              <Segmented className="ac-segmented" size="sm" ariaLabel={t("默认账号")} value={user} onChange={chooseUser}
                options={profiles.map((p) => ({ value: p.username, label: p.username }))} />
            </Row>
          )}
          {profiles.length === 1 && (
            <Row label={t("默认账号")}><span className="ac-mono">{user}</span></Row>
          )}
          {!profiles.length && !error && (
            <p style={{ color: 'var(--ac-sub)', fontSize: 13 }}>{t("还没有 profile。到 Upload-Post 创建一个，并连接要发布的账号。")}</p>
          )}
          {connected.length > 0 && (
            <Row label={t("选择要发布的平台")} stack>
              <div className="ac-seg ac-seg--sm ac-segmented" role="group" aria-label={t("选择要发布的平台")}>
                {connected.map((p) => (
                  <button key={p} type="button" aria-pressed={selected.includes(p)} onClick={() => toggle(p)}>{platformLabel(p)}</button>
                ))}
              </div>
            </Row>
          )}
          {profiles.length > 0 && !connected.length && (
            <p style={{ color: 'var(--ac-sub)', fontSize: 13 }}>{t("这个账号还没有连接平台。")}</p>
          )}
          <Row label={t("可见范围")} hint={t("默认先发到自己看得到的地方。公开会直接出现在账号上。")}>
            <Segmented size="sm" ariaLabel={t("可见范围")} value={visibility} onChange={setVisibility}
              options={[{ value: 'private', label: t("仅自己") }, { value: 'public', label: t("公开") }]} />
          </Row>
          <Row wide label={t("标题")} hint={t("不填就用切片标题。")}>
            <input className="ac-input" aria-label={t("标题")} value={title} onChange={(e) => setTitle(e.target.value)} />
          </Row>
          <Row wide label={t("描述")} hint={t("只有 YouTube、LinkedIn、Facebook、Pinterest 会用到。")}>
            <textarea className="ac-input ac-textarea" style={{ minHeight: 72 }} aria-label={t("描述")} value={description} onChange={(e) => setDescription(e.target.value)} />
          </Row>
          <p style={{ marginTop: 12, color: 'var(--ac-sub)', fontSize: 13 }}>
            {t("按「{{preset}}」预设渲成片。相同参数会复用已经导出的文件。", { preset: presetName })}
            {preset === 'shorts' ? ` ${t("竖屏平台会渲成 9:16，最长约 60 秒。")}` : ''}
            {preset === 'original' ? ` ${t("这次按原画重编码，不裁切。")}` : ''}
          </p>
        </>
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
              <div key={r.platform} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', padding: '8px 0', borderTop: '1px solid var(--ac-line)' }}>
                <StatusDot tone={tone} label={<>{platformLabel(r.platform)}{note ? <span style={{ color: 'var(--ac-muted)' }}> · {note}</span> : null}</>} />
                {r.url && (
                  <a href={r.url} onClick={(e) => { e.preventDefault(); void openExternalLink(r.url!) }} style={{ color: 'var(--ac-accent)', fontSize: 13 }}>{t("打开链接")}</a>
                )}
              </div>
            )
          })}
        </div>
      )}
      {error && <p style={{ marginTop: 12, color: 'var(--ac-error)', fontSize: 13 }}>{error}</p>}
    </Dialog>
  )
}

export default PublishAbroadDialog
