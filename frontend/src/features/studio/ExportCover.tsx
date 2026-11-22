import { useCallback, useEffect, useRef, useState } from 'react'
import { message } from 'antd'
import { t } from '../../i18n'
import { coverApi, type CoverDesign } from '../../publish/coverApi'
import api from '../../services/api'
import { Btn, Dialog } from '../../ui'
import { exportCoverSlot, studioApi } from './api'
import { isDesktopDownload, saveLocalFile } from './nativeDownload'
import type { OutputVariant, RenderJob } from './types'

type Props = {
  projectId: string; job: RenderJob; variant?: OutputVariant
  coverStamp?: number; onCoverChanged?: () => void
}

export function coverWarningMessage(
  warning?: string | null,
  cfg?: { enabled?: boolean; configured?: boolean; allow_send_frame?: boolean } | null,
): string {
  if (!warning) {
    return cfg?.enabled && cfg?.configured && cfg.allow_send_frame === false
      ? t('已关闭上传参考帧，当前使用本地排版封面')
      : ''
  }
  if (warning === 'frame_sending_disabled') return t('已关闭上传参考帧，当前使用本地排版封面')
  if (warning === 'needs_source_validation') return t('当前是截帧封面')
  if (warning === 'text_unavailable' || warning === 'text_mismatch') return t('生图标题校对未通过，已改成本地排版')
  if (
    warning === 'cover_photo_degraded' ||
    warning === 'cover_layout_changed' ||
    warning === 'subject_changed' ||
    warning === 'fidelity_unavailable'
  ) {
    return t(warning)
  }
  return t('生图失败，已改成本地排版或截帧')
}

export function coverStatusMessages(
  warning?: string | null,
  cfg?: { enabled?: boolean; configured?: boolean; allow_send_frame?: boolean } | null,
): string[] {
  const primary = coverWarningMessage(warning, cfg)
  const messages = primary ? [primary] : []
  const optOut = cfg?.enabled && cfg?.configured && cfg.allow_send_frame === false
    ? t('已关闭上传参考帧，当前使用本地排版封面')
    : ''
  if (optOut && warning === 'needs_source_validation' && !messages.includes(optOut)) {
    messages.push(optOut)
  }
  return messages
}

export function resolvedCoverTitle(headline: string | null, savedTitle: string, jobTitle?: string): string | undefined {
  const raw = headline === null ? (savedTitle || jobTitle || '') : headline
  return raw.trim() || undefined
}

/** Reads the cover made for this export. Older exports can generate their missing cover here. */
export default function ExportCover({ projectId, job, variant, coverStamp = 0, onCoverChanged }: Props) {
  const clip = `studio-${job.job_id}`
  const platform = exportCoverSlot(job)
  const [version, setVersion] = useState(coverStamp)
  const [failedUrl, setFailedUrl] = useState('')
  const [loadedUrl, setLoadedUrl] = useState('')
  const [task, setTask] = useState<{ id: string; variantId?: string } | null>(null)
  const [missingVariantFile, setMissingVariantFile] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [headline, setHeadline] = useState<string | null>(null)
  const [savedTitle, setSavedTitle] = useState('')
  const [askReference, setAskReference] = useState(false)
  const [referenceOnce, setReferenceOnce] = useState(false)
  const [design, setDesign] = useState<CoverDesign>({ mode: 'crop_grade_text_only', recipe: 'auto' })
  const [times, setTimes] = useState<number[]>([])
  const [frameLocked, setFrameLocked] = useState(false)
  const [warning, setWarning] = useState('')
  const [statusNotices, setStatusNotices] = useState<string[]>([])
  const variantId = variant?.id
  useEffect(() => {
    let active = true
    const current = variantId ? studioApi.variantCoverDesign(projectId, variantId) : coverApi.get(projectId, clip, platform)
    void Promise.all([current.catch(() => null), coverApi.getConfig().catch(() => null)]).then(([view, cfg]) => {
      if (!active) return
      setSavedTitle(view?.headline || view?.title || '')
      setDesign(view?.options || { mode: cfg?.design_mode || 'crop_grade_text_only', recipe: 'auto' })
      setTimes(view?.candidate_times || [])
      setFrameLocked(!!view?.frame_locked)
      setWarning(coverWarningMessage(view?.warning, cfg))
      setStatusNotices(coverStatusMessages(view?.warning, cfg))
      setAskReference(!!cfg?.enabled && cfg.configured && !cfg.allow_send_frame)
      setReferenceOnce(false)
    })
    return () => { active = false }
  }, [projectId, clip, platform, variantId, version])
  const mounted = useRef(false)
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])
  const variantPath = variant && !missingVariantFile
    ? `/studio/${projectId}/output-variants/${variant.id}/cover` : ''
  const path = variantPath || `/publish/covers/${projectId}/clips/${clip}/file?platform=${platform}`
  const url = `${api.defaults.baseURL}${path}${path.includes('?') ? '&' : '?'}v=${variant?.cover || ''}-${version}`
  const pending = job.cover_pending || busy || !!task || ['queued', 'running'].includes(variant?.cover_job?.status || '')
  const missing = failedUrl === url

  useEffect(() => {
    if (!task) return
    let closed = false
    let timer: number
    const check = async () => {
      try {
        const state = task.variantId ? await studioApi.variantCoverJob(projectId, task.variantId) : await coverApi.job(task.id)
        if (closed) return
        if (state.status === 'queued' || state.status === 'running') {
          timer = window.setTimeout(check, 1200)
          return
        }
        if (state.status === 'completed') {
          if (task.variantId) {
            setMissingVariantFile(false)
          }
          onCoverChanged?.()
          setVersion(v => v + 1)
        }
        else setError(state.error || t('封面生成失败，请重试'))
      } catch {
        if (closed) return
        setError(t('封面生成失败，请重试'))
      }
      setTask(null)
    }
    void check()
    return () => { closed = true; window.clearTimeout(timer) }
  }, [projectId, task, onCoverChanged])

  const generate = async () => {
    setBusy(true)
    setError('')
    const title = resolvedCoverTitle(headline, savedTitle, job.title)
    try {
      if (variant) {
        const result = await studioApi.redesignVariantCover(projectId, variant.id, { design, title, allow_reference_once: referenceOnce })
        if (!mounted.current) return
        setReferenceOnce(false)
        setTask({ id: result.job_id, variantId: variant.id })
        return
      }
      const result = await coverApi.start(projectId, clip, { platform, design, title, allow_reference_once: referenceOnce })
      if (!mounted.current) return
      setReferenceOnce(false)
      if ('job_id' in result) setTask({ id: result.job_id })
      else if (result.ok) { setVersion(v => v + 1); onCoverChanged?.() }
      else setError(t('封面生成失败，请重试'))
    } catch {
      if (mounted.current) setError(t('封面生成失败，请重试'))
    } finally { if (mounted.current) setBusy(false) }
  }
  return <section className="studio-export-cover" aria-label={t('封面')}>
    <div><b>{t('封面')}</b>
      {pending ? <span role="status">{t('正在生成封面')}</span> : missing
        ? <Btn size="sm" onClick={generate}>{t('生成封面')}</Btn>
        : loadedUrl === url && <a className="ac-btn ac-btn--sm" href={url} download={`${clip}.jpg`} onClick={event => {
          if (!isDesktopDownload()) return
          event.preventDefault()
          void saveLocalFile(path).then(() => message.success(t('封面已保存')), () => message.error(t('下载失败，请稍后重试')))
        }}>{t('下载封面')}</a>}
      {!pending && !missing && loadedUrl === url && <Btn size="sm" variant="text" onClick={generate}>{t('重新生成封面')}</Btn>}
    </div>
    {!pending && !missing && <img src={url} alt={t('封面')} onLoad={() => setLoadedUrl(url)} onError={() => { if (variantPath) setMissingVariantFile(true); else setFailedUrl(url) }} />}
    {!pending && (statusNotices.length > 0 ? statusNotices : (warning ? [warning] : [])).map(note => (
      <span key={note} role="status" className="studio-muted">{note}</span>
    ))}
    {!pending && <div className="studio-cover-fields">
      <label>{t('封面标题')}<input className="ac-input" value={headline ?? savedTitle} placeholder={job.title}
        maxLength={100} onChange={e => setHeadline(e.target.value)} /></label>
      <label>{t('封面风格')}<select value={design.recipe} onChange={e => setDesign({ ...design, recipe: e.target.value as CoverDesign['recipe'] })}>
        {([['auto','自动'],['photo_focus','原帧排版'],['culture_editorial','文化访谈'],['tech_question','观点提问'],['bold_statement','鲜明态度']] as const)
          .map(([value,label]) => <option key={value} value={value}>{t(label)}</option>)}</select></label>
      <label>{t('封面制作方式')}<select value={design.mode} onChange={e => setDesign({ ...design, mode: e.target.value as CoverDesign['mode'] })}>
        <option value="crop_grade_text_only">{t('原帧排版')}</option><option value="editorial_edit">{t('模型编辑')}</option></select></label>
      <label>{t('封面取帧')}<select disabled={frameLocked} value={design.frame_time ?? (design.change_frame ? 'next' : '')}
        onChange={e => setDesign({ ...design, change_frame: e.target.value === 'next', frame_time: !e.target.value || e.target.value === 'next' ? undefined : Number(e.target.value) })}>
        <option value="">{t('保留当前帧')}</option><option value="next">{t('重选镜头')}</option>
        {times.map(at => <option key={at} value={at}>{at.toFixed(2)} s</option>)}</select></label>
      {askReference && design.mode === 'editorial_edit' && <label><input type="checkbox" checked={referenceOnce} onChange={e => setReferenceOnce(e.target.checked)} /> {t('仅本次将所选视频帧发送给封面模型')}</label>}
    </div>}
    {error && <p className="studio-error" role="alert">{error}</p>}
  </section>
}

export function ExportCoverButton(props: Props) {
  const { projectId, job, variant, coverStamp = 0 } = props
  const [open, setOpen] = useState(false)
  const [failedVariant, setFailedVariant] = useState('')
  const [failedFile, setFailedFile] = useState('')
  const [updated, setUpdated] = useState(0)
  const { onCoverChanged } = props
  const refresh = useCallback(() => { setUpdated(Date.now()); onCoverChanged?.() }, [onCoverChanged])
  const stamp = Math.max(coverStamp, updated)
  const version = stamp || job.cover_revision || ''
  const variantUrl = variant && studioApi.variantCover(projectId, variant.id, stamp)
  const fallback = studioApi.kitUrl(`/publish/covers/${projectId}/clips/studio-${job.job_id}/file?platform=${exportCoverSlot(job)}&v=${encodeURIComponent(version)}`)
  const src = variantUrl && variantUrl !== failedVariant ? variantUrl : fallback
  return <><button type="button" className="studio-cover-preview" aria-haspopup="dialog" onClick={() => setOpen(true)}>
      {failedFile !== src && <img src={src} alt="" onError={() => {
        if (src === variantUrl) setFailedVariant(src)
        else setFailedFile(src)
      }} />}
      <span>{t(failedFile === src ? '生成封面' : '查看封面')}</span>
    </button>
    {open && <Dialog open onClose={() => setOpen(false)} title={t('封面')}>
      <ExportCover key={job.job_id} {...props} coverStamp={stamp} onCoverChanged={refresh} />
    </Dialog>}
  </>
}
