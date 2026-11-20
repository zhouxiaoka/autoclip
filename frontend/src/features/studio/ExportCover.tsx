import { useEffect, useRef, useState } from 'react'
import { message } from 'antd'
import { t } from '../../i18n'
import { coverApi } from '../../publish/coverApi'
import api from '../../services/api'
import { Btn, Dialog } from '../../ui'
import { studioApi } from './api'
import { isDesktopDownload, saveLocalFile } from './nativeDownload'
import type { OutputVariant, RenderJob } from './types'

type Props = { projectId: string; job: RenderJob; variant?: OutputVariant }

/** Reads the cover made for this export. Older exports can generate their missing cover here. */
export default function ExportCover({ projectId, job, variant }: Props) {
  const clip = `studio-${job.job_id}`
  const platform = job.result && job.result.height > job.result.width ? 'douyin' : 'bilibili'
  const [version, setVersion] = useState(0)
  const [failedUrl, setFailedUrl] = useState('')
  const [loadedUrl, setLoadedUrl] = useState('')
  const [task, setTask] = useState<{ id: string; variantId?: string } | null>(null)
  const [imageModel, setImageModel] = useState(false)
  const [useVariantFile, setUseVariantFile] = useState(false)
  const [missingVariantFile, setMissingVariantFile] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const mounted = useRef(false)
  useEffect(() => {
    mounted.current = true
    let current = true
    coverApi.getConfig().then(config => { if (current) setImageModel(config.configured && config.enabled) }).catch(() => {})
    return () => { current = false; mounted.current = false }
  }, [])
  const variantPath = variant && (variant.cover || useVariantFile) && !missingVariantFile
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
          if (task.variantId) { setUseVariantFile(true); setMissingVariantFile(false) }
          setVersion(v => v + 1)
        }
        else setError(t('封面生成失败，请重试'))
      } catch {
        if (closed) return
        setError(t('封面生成失败，请重试'))
      }
      setTask(null)
    }
    void check()
    return () => { closed = true; window.clearTimeout(timer) }
  }, [projectId, task])

  const generate = async () => {
    setBusy(true)
    setError('')
    try {
      if (variant && imageModel) {
        const result = await studioApi.redesignVariantCover(projectId, variant.id)
        if (mounted.current) setTask({ id: result.job_id, variantId: variant.id })
        return
      }
      const result = await coverApi.start(projectId, clip, { platform, title: job.title })
      if (!mounted.current) return
      if ('job_id' in result) setTask({ id: result.job_id })
      else if (result.ok) setVersion(v => v + 1)
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
      {!pending && !missing && loadedUrl === url && imageModel && <Btn size="sm" variant="text" onClick={generate}>{t('AI 重新设计封面')}</Btn>}
    </div>
    {!pending && !missing && <img src={url} alt={t('封面')} onLoad={() => setLoadedUrl(url)} onError={() => { if (variantPath) setMissingVariantFile(true); else setFailedUrl(url) }} />}
    {!pending && variant?.cover_job?.status === 'failed' && !missing && <span className="studio-muted">{t('生图失败，已改成本地排版或截帧')}</span>}
    {error && <p className="studio-error" role="alert">{error}</p>}
  </section>
}

export function ExportCoverButton(props: Props) {
  const [open, setOpen] = useState(false)
  return <><Btn size="sm" onClick={() => setOpen(true)}>{t('查看封面')}</Btn>
    {open && <Dialog open onClose={() => setOpen(false)} title={t('查看封面')}>
      <ExportCover key={props.job.job_id} {...props} />
    </Dialog>}
  </>
}
