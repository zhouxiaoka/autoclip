import { useEffect, useRef, useState } from 'react'
import { message } from 'antd'
import { t } from '../../i18n'
import { Btn } from '../../ui'
import { studioApi } from './api'
import { copyText } from './outputShare'
import { isDesktopDownload, saveLocalFile } from './nativeDownload'
import type { OutputVariant, PostCopy } from './types'
import { studioDownloadRequested, observeStudioDownload, type VariantProperties } from '../../analytics/studio'

const LANDSCAPE = new Set(['bilibili', 'youtube_long', 'original'])

/** Post copy as it is pasted into a platform: title, description, then the hashtags. */
export function postCaption(post: PostCopy) {
  return [post.title, post.description, post.tags.map(tag => `#${tag}`).join(' ')].filter(Boolean).join('\n\n')
}

/** Ready-to-publish copy and cover of one output: read, edit, copy, export as a bundle, redo the cover with AI. */
export default function PublishKit({ projectId, variant, analytics = {}, coverStamp, onCoverChanged, onCopied }: { projectId: string; variant: OutputVariant; analytics?: VariantProperties; coverStamp: number; onCoverChanged: () => void; onCopied: () => void }) {
  // A saved edit shows right away: the workspace stops polling once every output is done.
  const [saved, setSaved] = useState<PostCopy | null>(null)
  useEffect(() => setSaved(null), [variant.post])
  const post = saved || variant.post
  const [editing, setEditing] = useState(false)
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const [draft, setDraft] = useState<PostCopy | null>(post || null)
  const [saving, setSaving] = useState(false)
  const [redesigning, setRedesigning] = useState(false)
  useEffect(() => { if (!editing) setDraft(post || null) }, [post, editing])
  if (!post || !draft) return null
  const save = async () => {
    setSaving(true)
    try {
      setSaved(await studioApi.updateVariantPost(projectId, variant.id, draft))
      setEditing(false)
      message.success(t('文案已保存'))
    } catch {
      message.error(t('保存失败，请稍后重试'))
    } finally { setSaving(false) }
  }
  const copy = async () => {
    if (await copyText(postCaption(post))) { onCopied(); message.success(t('发布文案已复制')) }
    else message.error(t('复制失败，请稍后重试'))
  }
  const kitPath = `/studio/${projectId}/output-variants/${variant.id}/kit`
  const coverUrl = studioApi.variantCover(projectId, variant.id, coverStamp)
  const exportKit = async (event: React.MouseEvent) => {
    const props = { ...analytics, strategy_id: variant.strategy_id, artifact_type: 'publish_kit' as const }
    if (!isDesktopDownload()) { studioDownloadRequested(projectId, variant.render_job_id, props); return }
    event.preventDefault()
    try { await observeStudioDownload(() => saveLocalFile(kitPath), projectId, variant.render_job_id, props); message.success(t('发布包已保存到下载文件夹')) } catch { message.error(t('下载失败，请稍后重试')) }
  }
  const redesign = async () => {
    if (!variant.render_job_id) return
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
      if (!done) { message.info(t('AI 封面还在生成，稍后刷新查看')); return }
      onCoverChanged()
      message.success(t('封面已用 AI 重新设计'))
    } catch {
      if (mounted.current) message.error(t('AI 封面没有生成成功，可以在设置里检查图像模型'))
    } finally { if (mounted.current) setRedesigning(false) }
  }
  return <div className="studio-post">
    {editing ? <div className="studio-post-edit">
      <input className="ac-input" aria-label={t('标题')} value={draft.title} onChange={event => setDraft({ ...draft, title: event.target.value })}/>
      <textarea className="ac-input ac-textarea" aria-label={t('简介')} value={draft.description} onChange={event => setDraft({ ...draft, description: event.target.value })}/>
      <input className="ac-input" aria-label={t('话题')} value={draft.tags.join(' ')} placeholder={t('话题，用空格分隔')}
        onChange={event => setDraft({ ...draft, tags: event.target.value.split(/[\s,，#]+/).filter(Boolean) })}/>
      <div className="studio-post-actions"><Btn variant="text" onClick={() => { setDraft(post); setEditing(false) }}>{t('取消')}</Btn><Btn size="sm" loading={saving} onClick={() => void save()}>{t('保存')}</Btn></div>
    </div> : <>
      <div className="studio-post-body">
        {variant.cover && <a className={`studio-post-cover${LANDSCAPE.has(variant.strategy_id) ? ' studio-post-cover--wide' : ''}`} href={coverUrl} target="_blank" rel="noreferrer" title={t('查看封面')}>
          <img src={coverUrl} alt={t('封面')}/>
        </a>}
        <div className="studio-post-text">
          <h2 className="studio-post-title" title={post.title}>{post.title}</h2>
          {post.description && <p className="studio-post-desc">{post.description}</p>}
          {post.tags.length > 0 && <p className="studio-post-tags" title={post.tags.map(tag => `#${tag}`).join(' ')}>{post.tags.map(tag => `#${tag}`).join(' ')}</p>}
        </div>
      </div>
      <div className="studio-post-actions">
        <Btn variant="text" onClick={() => void copy()}>{t('复制发布文案')}</Btn>
        <Btn variant="text" onClick={() => setEditing(true)}>{t('编辑文案')}</Btn>
        {variant.status === 'completed' && <a className="studio-link" href={studioApi.variantKit(projectId, variant.id)} download onClick={event => void exportKit(event)}>{t('导出发布包')}</a>}
        {variant.status === 'completed' && <Btn variant="text" loading={redesigning} onClick={() => void redesign()}>{t('AI 重新设计封面')}</Btn>}
      </div>
    </>}
  </div>
}
