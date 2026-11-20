import { useEffect, useRef, useState } from 'react'
import { message } from 'antd'
import { t } from '../../i18n'
import { Btn, Dialog } from '../../ui'
import { studioApi } from './api'
import { copyText } from './outputShare'
import { isDesktopDownload, saveLocalFile, saveStudioExport } from './nativeDownload'
import type { OutputVariant, PostCopy, RenderJob } from './types'
import { ExportCoverButton } from './ExportCover'
import { studioDownloadRequested, observeStudioDownload, type VariantProperties } from '../../analytics/studio'
import { flagAssigned, useFlag } from '../../analytics/flags'
import { trackAutoChoiceOverridden } from '../../analytics/studio'
import { markOutputTaken } from './overrides'
import { captionWithCredit, savePublishPack } from './publishPack'

const LANDSCAPE = new Set(['bilibili', 'youtube_long', 'original'])

/** Post copy as it is pasted into a platform: title, description, then the hashtags. */
export function postCaption(post: PostCopy) {
  return [post.title, post.description, post.tags.map(tag => `#${tag}`).join(' ')].filter(Boolean).join('\n\n')
}

/** Ready-to-publish copy and cover of one output: read, edit, copy, export as a bundle, redo the cover with AI. */
export default function PublishKit({ projectId, variant, job, post, onPostChange, analytics = {}, coverStamp, onCoverChanged, onCopied, onCombined }: { projectId: string; variant: OutputVariant; job?: RenderJob; post?: PostCopy | null; onPostChange: (post: PostCopy) => void; analytics?: VariantProperties; coverStamp: number; onCoverChanged: () => void; onCopied: () => void; onCombined?: () => void }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState({ title: '', description: '', tags: '' })
  const [saveError, setSaveError] = useState(false)
  const [saving, setSaving] = useState(false)
  const [packing, setPacking] = useState(false)
  const combined = useFlag('publish_pack_v2') === 'combined'
  const coverTools = variant.status === 'completed' && variant.render_job_id
    ? <CoverRedesign projectId={projectId} variant={variant} onCoverChanged={onCoverChanged}/> : null
  const coverUrl = studioApi.variantCover(projectId, variant.id, coverStamp)
  const noteCover = combined && variant.strategy_id === 'xiaohongshu'
  const thumbnail = (variant.cover || coverStamp > 0) && <span className={`studio-post-cover${noteCover ? ' studio-post-cover--note' : LANDSCAPE.has(variant.strategy_id) ? ' studio-post-cover--wide' : ''}`}>
    <img src={coverUrl} alt=""/>
  </span>
  const preview = job
    ? <ExportCoverButton projectId={projectId} job={job} variant={variant} coverStamp={coverStamp} onVariantCoverChanged={onCoverChanged}>{thumbnail}</ExportCoverButton>
    : thumbnail && <a href={coverUrl} target="_blank" rel="noreferrer" aria-label={t('查看封面')}>{thumbnail}</a>
  if (!post) return <>{preview}{coverTools}</>
  const edit = () => {
    setDraft({ title: post.title, description: post.description, tags: post.tags.join(' ') })
    setSaveError(false)
    setEditing(true)
  }
  const save = async () => {
    if (saving || !draft.title.trim()) return
    setSaveError(false)
    setSaving(true)
    try {
      onPostChange(await studioApi.updateVariantPost(projectId, variant.id, {
        title: draft.title.trim(), description: draft.description, tags: draft.tags.split(/[\s,，#]+/).filter(Boolean),
      }))
      if (draft.title !== post.title) trackAutoChoiceOverridden({ field: 'title', stage: 'results_chip' }, flagAssigned('track_overrides'))
      setEditing(false)
      message.success(t('文案已保存'))
    } catch {
      setSaveError(true)
    } finally { setSaving(false) }
  }
  const copy = async () => {
    if (await copyText(postCaption(post))) { markOutputTaken(projectId); onCopied(); message.success(t('发布文案已复制')) }
    else message.error(t('复制失败，请稍后重试'))
  }
  const kitPath = `/studio/${projectId}/output-variants/${variant.id}/kit`
  const saveCombined = async () => {
    if (!variant.render_job_id || packing) return
    if (!(await copyText(captionWithCredit(postCaption(post), variant.strategy_id)))) { message.error(t('复制失败，请稍后重试')); return }
    markOutputTaken(projectId)
    onCombined?.()
    setPacking(true)
    const coverPath = `/studio/${projectId}/output-variants/${variant.id}/cover`
    try {
      const mode = await savePublishPack({
        desktop: isDesktopDownload(),
        strategyId: variant.strategy_id,
        hasCover: !!variant.cover || coverStamp > 0,
        saveVideo: () => saveStudioExport(projectId, variant.render_job_id!),
        saveCover: () => saveLocalFile(coverPath),
        requestDownload: artifact => studioDownloadRequested(projectId, variant.render_job_id, { ...analytics, strategy_id: variant.strategy_id, artifact_type: artifact }),
        observeDownload: (action, artifact) => observeStudioDownload(action, projectId, variant.render_job_id, { ...analytics, strategy_id: variant.strategy_id, artifact_type: artifact }),
        openBrowser: kind => {
          const link = document.createElement('a')
          link.href = kind === 'video' ? studioApi.video(projectId, variant.render_job_id!, true) : coverUrl
          link.download = ''
          document.body.appendChild(link)
          link.click()
          link.remove()
        },
      })
      message.success(t(mode === 'native' ? '文案已复制，视频和封面已保存' : '发布文案已复制'))
    } catch {
      message.error(t('下载失败，请稍后重试'))
    } finally { setPacking(false) }
  }
  const exportKit = async (event: React.MouseEvent) => {
    markOutputTaken(projectId)
    const props = { ...analytics, strategy_id: variant.strategy_id, artifact_type: 'publish_kit' as const }
    if (!isDesktopDownload()) { studioDownloadRequested(projectId, variant.render_job_id, props); return }
    event.preventDefault()
    try { await observeStudioDownload(() => saveLocalFile(kitPath), projectId, variant.render_job_id, props); message.success(t('发布包已保存到下载文件夹')) } catch { message.error(t('下载失败，请稍后重试')) }
  }
  return <div className="studio-post">
    <Dialog open={editing} onClose={() => { if (!saving) setEditing(false) }} title={t('编辑文案')} footer={<>
      <Btn disabled={saving} onClick={() => setEditing(false)}>{t('取消')}</Btn>
      <Btn variant="cta" loading={saving} disabled={!draft.title.trim()} onClick={() => void save()}>{t('保存')}</Btn>
    </>}>
      <div className="studio-post-edit">
        <label>{t('标题')}<input className="ac-input" maxLength={100} value={draft.title} onChange={event => setDraft({ ...draft, title: event.target.value })}/></label>
        <label>{t('简介')}<textarea className="ac-input ac-textarea" rows={4} maxLength={2000} value={draft.description} onChange={event => setDraft({ ...draft, description: event.target.value })}/></label>
        <label>{t('话题')}<input className="ac-input" value={draft.tags} placeholder={t('话题，用空格分隔')}
          onChange={event => setDraft({ ...draft, tags: event.target.value })}/></label>
        {saveError && <p className="studio-error" role="alert">{t('保存失败，请稍后重试')}</p>}
      </div>
    </Dialog>
    <div className="studio-post-body">
      {preview}
      <div className="studio-post-text">
        <h2 className="studio-post-title" title={post.title}>{post.title}</h2>
        {post.description && <p className="studio-post-desc">{post.description}</p>}
        {post.tags.length > 0 && <p className="studio-post-tags" title={post.tags.map(tag => `#${tag}`).join(' ')}>{post.tags.map(tag => `#${tag}`).join(' ')}</p>}
      </div>
    </div>
    <div className="studio-post-actions">
      {combined && variant.status === 'completed' && variant.render_job_id
        ? <Btn className="studio-pack-action" loading={packing} onClick={() => saveCombined()}>{t('复制文案并保存视频和封面')}</Btn>
        : <Btn size="sm" onClick={() => void copy()}>{t('复制发布文案')}</Btn>}
      <Btn size="sm" variant="text" onClick={edit}>{t('编辑文案')}</Btn>
      {!combined && variant.status === 'completed' && <a className="studio-link" href={studioApi.variantKit(projectId, variant.id)} download onClick={event => void exportKit(event)}>{t('导出发布包')}</a>}
    </div>
    {coverTools}
  </div>
}

function CoverRedesign({ projectId, variant, onCoverChanged }: {
  projectId: string; variant: OutputVariant; onCoverChanged: () => void
}) {
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const [redesigning, setRedesigning] = useState(false)
  const [coverError, setCoverError] = useState('')
  const redesign = async () => {
    if (!variant.render_job_id || redesigning) return
    setCoverError('')
    setRedesigning(true)
    try {
      let job = await studioApi.redesignVariantCover(projectId, variant.id)
      let done = job.status === 'completed'
      for (let tries = 0; !done && tries < 90; tries++) {
        if (job.status === 'failed') throw new Error(job.error || 'failed')
        await new Promise(resolve => setTimeout(resolve, 2000))
        if (!mounted.current) return
        job = await studioApi.variantCoverJob(projectId, variant.id)
        done = job.status === 'completed'
      }
      if (!mounted.current) return
      if (job.status === 'failed') throw new Error(job.error || 'failed')
      if (!done) { message.info(t('正在生成封面')); return }
      onCoverChanged()
      message.success(t('封面已重新生成'))
    } catch {
      if (mounted.current) setCoverError(t('封面生成失败，请重试'))
    } finally { if (mounted.current) setRedesigning(false) }
  }
  return <div className="studio-cover-tools">
    <Btn variant="text" size="sm" loading={redesigning} onClick={() => void redesign()}>{t('重新生成封面')}</Btn>
    {coverError && <span role="alert">{coverError}</span>}
  </div>
}
