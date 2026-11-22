import { useState } from 'react'
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

/** Post copy as it is pasted into a platform: title, description, then the hashtags. */
export function postCaption(post: PostCopy) {
  return [post.title, post.description, post.tags.map(tag => `#${tag}`).join(' ')].filter(Boolean).join('\n\n')
}

/** Ready-to-publish copy and cover of one output: read, edit, copy, export as a bundle, redo the cover with AI. */
export default function PublishKit({ projectId, variant, job, post, onPostChange, analytics = {}, coverStamp, onCoverChanged, onCopied, onCombined }: { projectId: string; variant?: OutputVariant; job: RenderJob; post: PostCopy; onPostChange: (post: PostCopy) => void; analytics?: VariantProperties; coverStamp: number; onCoverChanged: () => void; onCopied: () => void; onCombined?: () => void }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState({ title: '', description: '', tags: '' })
  const [saveError, setSaveError] = useState(false)
  const [saving, setSaving] = useState(false)
  const [packing, setPacking] = useState(false)
  const combined = useFlag('publish_pack_v2') === 'combined' && !!variant
  const jobId = job.job_id
  const coverUrl = variant ? studioApi.variantCover(projectId, variant.id, coverStamp) : undefined
  const preview = <ExportCoverButton projectId={projectId} job={job} variant={variant} coverStamp={coverStamp} onCoverChanged={onCoverChanged} />
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
      const updated = {
        title: draft.title.trim(), description: draft.description, tags: draft.tags.split(/[\s,，#]+/).filter(Boolean),
      }
      onPostChange(variant ? await studioApi.updateVariantPost(projectId, variant.id, updated)
        : await studioApi.updateExportPost(projectId, job.job_id, updated))
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
  const kitPath = variant ? `/studio/${projectId}/output-variants/${variant.id}/kit` : `/studio/${projectId}/jobs/${jobId}/kit`
  const saveCombined = async () => {
    if (!variant?.render_job_id || packing) return
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
        saveVideo: async () => { await saveStudioExport(projectId, variant.render_job_id!) },
        saveCover: async () => { await saveLocalFile(coverPath) },
        requestDownload: artifact => studioDownloadRequested(projectId, variant.render_job_id, { ...analytics, strategy_id: variant.strategy_id, artifact_type: artifact }),
        observeDownload: (action, artifact) => observeStudioDownload(action, projectId, variant.render_job_id, { ...analytics, strategy_id: variant.strategy_id, artifact_type: artifact }),
        openBrowser: kind => {
          const link = document.createElement('a')
          link.href = kind === 'video' ? studioApi.video(projectId, variant.render_job_id!, true) : (coverUrl || '')
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
    const props = { ...analytics, strategy_id: variant?.strategy_id, artifact_type: 'publish_kit' as const }
    if (!isDesktopDownload()) { studioDownloadRequested(projectId, jobId, props); return }
    event.preventDefault()
    try { await observeStudioDownload(() => saveLocalFile(kitPath), projectId, jobId, props); message.success(t('发布包已保存到下载文件夹')) } catch { message.error(t('下载失败，请稍后重试')) }
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
    <section className="studio-publish-section"><h2>{t('封面')}</h2>{preview}</section>
    <section className="studio-publish-section"><h2>{t('发布文案')}</h2>
      <div className="studio-post-text">
        <h3 className="studio-post-title">{post.title}</h3>
        {post.description && <p className="studio-post-desc">{post.description}</p>}
        {post.tags.length > 0 && <p className="studio-post-tags" title={post.tags.map(tag => `#${tag}`).join(' ')}>{post.tags.map(tag => `#${tag}`).join(' ')}</p>}
      </div>
    <div className="studio-post-actions">
      {combined && variant.status === 'completed' && variant.render_job_id
        ? <Btn className="studio-pack-action" loading={packing} onClick={() => saveCombined()}>{t('复制文案并保存视频和封面')}</Btn>
        : <Btn size="sm" onClick={() => void copy()}>{t('复制发布文案')}</Btn>}
      <Btn size="sm" variant="text" onClick={edit}>{t('编辑文案')}</Btn>
      {!combined && job.status === 'completed' && <a className="studio-link" href={studioApi.kitUrl(kitPath)} download onClick={event => void exportKit(event)}>{t('导出发布包')}</a>}
    </div>
    </section>
  </div>
}
