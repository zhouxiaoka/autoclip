import { useTranslation } from 'react-i18next'
import { getLocale, t } from '../../i18n'
import { ReactNode, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Project, Clip } from '../../store/useProjectStore'
import { Btn, Section, Dialog, fmtDuration } from '../../ui'
import { studioApi, errorText } from './api'
import { sourceFailure } from './importReadiness'
import { browserCookieRecovery, stageBrowserCookieRecovery } from './browserCookieRecovery'
import { diagnoseInsteadOfRetry, pageFailureAction, presentedFailure, RECHARGE_LABEL, receiptFailureInfo } from './failureAction'
import { countPreservedResults, presentFailure, resolveFailureCause } from './failurePresentation'
import { openExternalLink } from '../../utils/externalLinks'
import DiagnosePanel from './DiagnosePanel'
import SwitchModelDialog from './SwitchModelDialog'
import { listSwitchModelOptions, usableConnectionCount } from './switchModelOptions'
import { modelSettingsApi, type ModelSettings } from '../settings/modelSettingsApi'
import { forSave } from '../settings/modelSettingsLogic'
import { syncFollowingCover } from '../settings/modelDefaults'
import { displayedProgress, studioRunProgress } from './studioProgress'
import { recordSuccess } from './etaModel'
import { settingsReturnUrl } from './settingsReturn'
import { useWorkspace } from './useWorkspace'
import { Scene, Draft, type OutputVariant } from './types'
import ExportHistory from './ExportHistory'
import PlanEditDialog from './PlanEditDialog'
import PlanSummary from './PlanSummary'
import DraftResultCard from './DraftResultCard'
import OutputVariantCard from './OutputVariantCard'
import { platformLabel } from './platformLabel'
import { flagAssigned, flagEnabled } from '../../analytics/flags'
import { trackLegacyEntry } from '../../analytics/studio'
import { workflow } from '../../analytics/observer'
import { legacyEntrypointsHidden } from './legacyEntrypoints'
import { clearCompletionBadge, subscribeCompletionNotice, type NoticeKind } from './noticeRuntime'
import { noticeCopy } from './completionNotice'
import { dismissMorePlatformBanner, morePlatformBannerSeen, stashReuseImport, suggestAnotherPlatform } from './platformMemory'
import { followOutputLeave } from './overrides'
import FailureHint from '../diagnostics/FailureHint'
import { nextLiveFailure } from '../diagnostics/failureHintPolicy'

import './studio.css'
import './quick-output.css'

const REPLAY_SOURCE_LABELS: Record<string, string> = {
  obs: 'OBS Studio',
  twitch_archive: 'Twitch',
  twitch_file: 'Twitch',
  youtube_file: 'YouTube',
  kick_file: 'Kick',
  discord_file: 'Discord',
}

function GameplayReview({ projectId, variants, drafts }: { projectId: string; variants: OutputVariant[]; drafts: Draft[] }) {
  const navigate = useNavigate()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [failedVideo, setFailedVideo] = useState('')
  const playable = variants.filter(variant => variant.status === 'completed' && variant.render_job_id)
  // Group variants by draft so Next/Previous moves between distinct highlight moments
  // instead of making the user watch the same clip once per selected platform.
  const groups: { draftId: string; items: OutputVariant[] }[] = []
  for (const variant of playable) {
    const group = groups.find(item => item.draftId === variant.draft_id)
    if (group) group.items.push(variant)
    else groups.push({ draftId: variant.draft_id, items: [variant] })
  }
  const groupIndex = groups.findIndex(group => group.items.some(item => item.id === selectedId))
  const activeGroup = groups[groupIndex]
  const selected = activeGroup?.items.find(item => item.id === selectedId)
  const draft = selected && drafts.find(item => item.id === selected.draft_id)
  const title = selected?.post?.title || draft?.title || t('精彩高光')
  const sourceScenes = draft?.revision === selected?.draft_revision ? draft?.scenes : undefined
  const choose = (id: string) => {
    setFailedVideo('')
    setSelectedId(id)
  }
  if (!groups.length) return null
  return <>
    <Btn size="sm" onClick={event => {
      event.currentTarget.closest('.studio-results')?.querySelectorAll('video').forEach(video => video.pause())
      choose(groups[0].items[0].id)
    }}>{t('回看游戏高光')}</Btn>
    {selected?.render_job_id && <Dialog open onClose={() => setSelectedId(null)} title={title}
      description={`${groupIndex + 1} / ${groups.length} · ${platformLabel(selected.strategy_id)}`}
      footer={<div className="studio-actions">
        {groups.length > 1 && <>
          <Btn disabled={groupIndex === 0} onClick={() => choose(groups[groupIndex - 1].items[0].id)}>{t('上一个切片')}</Btn>
          <Btn disabled={groupIndex === groups.length - 1} onClick={() => choose(groups[groupIndex + 1].items[0].id)}>{t('下一个切片')}</Btn>
        </>}
        {draft && <Btn onClick={() => navigate(`/project/${projectId}/studio/${draft.id}?variant=${encodeURIComponent(selected.id)}`)}>{t('预览与修改')}</Btn>}
      </div>}>
      {activeGroup && activeGroup.items.length > 1 && <div className="studio-actions" style={{ marginBottom: 8 }}>
        {activeGroup.items.map(variant => <Btn key={variant.id} size="sm" variant={variant.id === selected.id ? 'cta' : undefined}
          onClick={() => choose(variant.id)}>{platformLabel(variant.strategy_id)}</Btn>)}
      </div>}
      <video key={selected.render_job_id} className="studio-source-video" controls playsInline preload="metadata"
        aria-label={title} src={studioApi.video(projectId, selected.render_job_id)} onError={() => setFailedVideo(selected.id)} />
      {failedVideo === selected.id && <p role="alert">{t('这个切片当前播放器无法解码，请下载后用系统播放器打开。')}</p>}
      {!!sourceScenes?.length && <p className="studio-muted">{t('原片')} · {sourceScenes.map(scene => `${fmtDuration(scene.start)}–${fmtDuration(scene.end)}`).join(' / ')}</p>}
    </Dialog>}
  </>
}

export default function StudioResults({ project, children, onCreateCollection, onReload }: { project: Project; children: ReactNode; onCreateCollection: () => void; onReload: () => void }) {
  useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const resumeAfterSettings = new URLSearchParams(location.search || '').get('continue') === '1'
  const {workspace,error,loading,loaded,refresh} = useWorkspace(project.id)
  const [remaking, setRemaking] = useState(false)
  const [history, setHistory] = useState(false)
  const [busy,setBusy] = useState('')
  const busyRef = useRef('')
  const [actionError,setActionError] = useState('')
  const [preview,setPreview] = useState<Scene|null>(null)
  const [exporting,setExporting] = useState<Draft|null>(null)
  const [aiSettings, setAiSettings] = useState<ModelSettings | null>(null)
  useEffect(() => {
    let live = true
    modelSettingsApi.get().then(v => { if (live) setAiSettings(v) }).catch(() => { if (live) setAiSettings(null) })
    return () => { live = false }
  }, [])
  const goal = project.settings?.creative?.goal || project.processing_config?.creative?.goal || 'content'
  const visual = goal !== 'content'
  const sourceDuration=workspace.plan?.source_duration ?? workspace.analysis?.coverage?.duration
  const managed = visual || !!project.settings?.smart_import || !!project.processing_config?.smart_import
  const automatic = !!workspace.generation?.auto_start
  const variants = workspace.output_variants || []
  const variantDraftIds = new Set(variants.map(v => v.draft_id).filter(Boolean))
  const standaloneDrafts = automatic ? [] : workspace.drafts.filter(d => !variantDraftIds.has(d.id))
  const showDraftList = !automatic && (standaloneDrafts.length > 0 || variants.length > 0)
  const legacyCount = (project.clips?.length || 0) + (project.collections?.length || 0)
  const completedExportCount = (workspace.jobs || []).filter(j => j.status === 'completed').length
  const resultCount = automatic ? variants.length : (variants.length + standaloneDrafts.length) || legacyCount
  const sourceCount = workspace.events.length + (showDraftList ? legacyCount : (project.clips?.length || 0))
  const hideLegacy = legacyEntrypointsHidden(flagEnabled('hide_legacy_entrypoints'), managed || automatic)
  const noteLegacy = (action: 'plan_adjust' | 'collection' | 'export_confirm') => trackLegacyEntry({ legacy_action: action }, flagAssigned('hide_legacy_entrypoints'))
  const taskFailed = workspace.analysis?.status === 'failed' || workspace.generation?.status === 'failed'
  const seenStatus = useRef<Record<string, string>>({})
  const [liveFailure, setLiveFailure] = useState(false)
  useEffect(() => {
    const step = nextLiveFailure(seenStatus.current, [{ id: project.id, status: taskFailed ? 'failed' : 'running' }])
    seenStatus.current = step.previous
    if (step.failed) setLiveFailure(true)
  }, [project.id, taskFailed])
  const failedCode = workspace.analysis?.error_code || workspace.generation?.error_code
  const sourceUnusable = workspace.analysis?.status === 'failed' && sourceFailure(failedCode)
  const cookieRecovery = workspace.analysis?.status === 'failed' && browserCookieRecovery(failedCode, workspace.analysis?.error)
  // the generation status covers this round only; earlier rounds' failures stay listed (count from settle)
  const notRedone = workspace.generation?.not_redone_failed_count || 0
  const attemptId = workspace.generation?.attempt_id
  const fallbackCount = workspace.attempts?.find(receipt => receipt.attempt_id === attemptId)?.summary?.packaging_fallback_count
  const incompletePackaging = (workspace.generation?.status === 'completed' || workspace.generation?.status === 'partial') &&
    (attemptId ? typeof fallbackCount === 'number' && fallbackCount > 0 : workspace.output_variants?.some(variant =>
      variant.status === 'completed' && workspace.drafts.some(draft =>
        draft.id === variant.draft_id && draft.revision === variant.draft_revision && draft.packaging?.fallback)))
  const outputStatus = workspace.generation?.status === 'completed' && notRedone > 0 ? t('本次重跑已完成，之前还有 {{count}} 条未完成版本可重试。', { count: notRedone })
    : workspace.generation?.status === 'completed' ? t(incompletePackaging ? '已导出 · 可下载' : '已按所选平台生成可发布成片。')
    : workspace.generation?.status === 'partial' ? t('部分成片已完成，未完成版本可稍后重试。')
      : workspace.generation?.status === 'failed' ? t(sourceUnusable ? '这个素材无法使用' : '这次制作未完成') : t('AI 正在按所选平台制作成片。')
  const generationDescription = incompletePackaging ? `${outputStatus} ${t('部分包装未完整生成，详情见下方成片。')}` : outputStatus
  const variantDraft = (draftId: string) => workspace.drafts.find(draft => draft.id === draftId)
  const variantJob = (jobId?: string) => workspace.jobs.find(job => job.job_id === jobId)
  const latest = useRef(workspace)
  latest.current = workspace
  const [doneNote, setDoneNote] = useState<NoticeKind | null>(null)
  useEffect(() => subscribeCompletionNotice((key, kind) => {
    if (key === project.id) setDoneNote(kind)
  }), [project.id])
  useEffect(() => {
    const clear = () => { if (document.visibilityState === 'visible') void clearCompletionBadge() }
    window.addEventListener('focus', clear)
    document.addEventListener('visibilitychange', clear)
    const stopLeave = followOutputLeave(project.id, () => {
      const current = latest.current
      return {
        createdAt: current.generation?.created_at,
        status: current.generation?.status,
        completed: (current.output_variants || []).filter(item => item.status === 'completed').length,
      }
    })
    return () => {
      window.removeEventListener('focus', clear)
      document.removeEventListener('visibilitychange', clear)
      stopLeave()
    }
  }, [project.id])
  // A retry whose response was lost is still watched: the open generation attempt on the snapshot is the source.
  useEffect(()=>{workflow.adoptOpenAttempt(project.id, workspace)},[project.id, workspace.attempts])
  useEffect(() => {
    const status = workspace.analysis?.status
    if (status === 'awaiting_confirmation' || (status && status !== 'running' && project.status !== 'completed')) onReload()
  }, [workspace.analysis?.status])
  const act = async (key: string, fn:()=>Promise<void>) => {
    if (busyRef.current) return
    busyRef.current = key
    setBusy(key);setActionError('');try{await fn();refresh()}catch(e){setActionError(t(errorText(e)))}finally{busyRef.current = '';setBusy('')}
  }
  const [progressNow, setProgressNow] = useState(() => Date.now())
  const progressRun = workspace.analysis?.status === 'running' || workspace.jobs.some(job => job.status === 'queued' || job.status === 'running')
  useEffect(() => {
    if (!progressRun) return
    const timer = window.setInterval(() => setProgressNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [progressRun])
  const progressFloor = useRef(0)
  const progressKey = `${project.id}:${workspace.analysis?.run_id || ''}:${workspace.analysis?.status || ''}`
  const progressKeySeen = useRef(progressKey)
  if (progressKeySeen.current !== progressKey) {
    progressKeySeen.current = progressKey
    progressFloor.current = 0
  }
  const progressRaw = studioRunProgress({
    analysis: workspace.analysis,
    generation: workspace.generation,
    jobs: workspace.jobs,
    source_duration_sec: typeof sourceDuration === 'number' ? sourceDuration : null,
    concurrency: 1,
  }, progressNow)
  const progressShown = progressRaw && displayedProgress(progressRaw, progressFloor.current)
  if (progressShown) progressFloor.current = progressShown.floor
  const progress = progressShown?.view ?? null
  const etaPosted = useRef('')
  useEffect(() => {
    const initial = progress?.etaInitialMin
    const attempt = workspace.generation?.attempt_id || workspace.analysis?.run_id || ''
    if (!initial || !attempt || etaPosted.current === attempt) return
    etaPosted.current = attempt
    void studioApi.reportEta(project.id, initial).catch(() => undefined)
  }, [progress?.etaInitialMin, workspace.generation?.attempt_id, workspace.analysis?.run_id, project.id])
  useEffect(() => {
    const status = workspace.generation?.status
    if (status !== 'completed' && status !== 'partial') return
    const provider = workspace.generation?.provider || workspace.analysis?.provider
    const sourceMin = typeof sourceDuration === 'number' && sourceDuration > 0 ? sourceDuration / 60 : 0
    const started = workspace.generation?.created_at || workspace.analysis?.created_at
    const stamp = workspace.generation?.attempt_id || started || ''
    if (!provider || !(sourceMin > 0) || !started || !stamp) return
    const storageKey = `autoclip.eta.recorded.${project.id}`
    try { if (sessionStorage.getItem(storageKey) === stamp) return } catch { /* ignore */ }
    const elapsed = Math.max(0, (Date.now() - Date.parse(started)) / 1000)
    if (!(elapsed > 0)) return
    try { sessionStorage.setItem(storageKey, stamp) } catch { /* ignore */ }
    recordSuccess({ provider, source_min: sourceMin, elapsed_sec: elapsed })
  }, [workspace.generation?.status, workspace.generation?.attempt_id, workspace.generation?.provider, workspace.generation?.created_at, workspace.analysis?.provider, workspace.analysis?.created_at, sourceDuration, project.id])

  const billable = Math.max(workspace.analysis?.billable_calls_before_failure || 0, workspace.generation?.billable_calls_before_failure || 0)
  const switchOptions = listSwitchModelOptions(aiSettings, {
    connectionId: aiSettings?.analysis?.connection_id,
    model: aiSettings?.analysis?.model,
  })
  const [diagnoseOpen, setDiagnoseOpen] = useState(false)
  const [switchOpen, setSwitchOpen] = useState(false)
  const receiptCause = receiptFailureInfo(workspace.attempts, workspace.analysis?.run_id)
  const resolvedCause = resolveFailureCause({
    analysis: workspace.analysis,
    generation: workspace.generation,
    receipt: receiptCause,
  })
  const completedVariants = (workspace.output_variants || []).filter(item => item.status === 'completed')
  const representedJobs = new Set(completedVariants.map(item => item.render_job_id).filter(Boolean))
  const preservedCount = countPreservedResults({
    drafts: workspace.drafts?.length,
    completedVariants: completedVariants.length,
    clips: project.clips?.length,
    collections: project.collections?.length,
    completedJobs: (workspace.jobs || []).filter(job => job.status === 'completed' && !representedJobs.has(job.job_id)).length,
  })
  const presented = presentFailure({
    ...resolvedCause,
    error: resolvedCause.error || workspace.analysis?.error,
    preservedCount,
    connectionCount: usableConnectionCount(aiSettings),
  })
  const detailView = resumeAfterSettings && presented.primary && (presented.primary.id === 'settings' || presented.primary.id === 'quota_check' || presented.primary.id === 'install_transcription')
    ? { ...presented, primary: { id: 'retry_production' as const, label: '重试制作' } }
    : presented
  const failureInfo = { ...resolvedCause, error: resolvedCause.error || workspace.analysis?.error }
  const failureBilling = presentedFailure(failureInfo, detailView.reason).billing
  const rawFailureAction = pageFailureAction(failureInfo)
  const rechargeUrl = preservedCount === 0 && detailView.primary?.id === 'quota_check' && rawFailureAction.kind === 'recharge' && /^https?:\/\//i.test(rawFailureAction.destination || '')
    ? (rawFailureAction.destination as string)
    : ''
  const rechargeLabel = rawFailureAction.kind === 'recharge' ? (rawFailureAction.label || RECHARGE_LABEL) : RECHARGE_LABEL
  const isRetryPrimary = preservedCount === 0 && (detailView.primary?.id === 'retry' || detailView.primary?.id === 'retry_production')
  const resumePoint = isRetryPrimary && workspace.resume_point?.point && workspace.resume_point.point !== 'none'
    ? workspace.resume_point
    : null
  const escalateDiagnose = isRetryPrimary && diagnoseInsteadOfRetry(workspace.generation?.repeat_failure)
  const switchModelAndRetry = async (choice: { connectionId: string; model: string }) => {
    if (!aiSettings) return
    const saved = await modelSettingsApi.save(forSave(syncFollowingCover(aiSettings, {
      ...aiSettings,
      analysis: {
        connection_id: choice.connectionId,
        model: choice.model,
        capability: aiSettings.analysis?.capability || 'auto',
        model_source: 'user',
      },
    })), forSave(aiSettings))
    setAiSettings(saved)
    await studioApi.retry(project.id, { retry_kind: 'switch_model' })
  }
  const createLegacy = (clip: Clip) => act(clip.id, async()=>{const draft=await studioApi.create(project.id,[clip.id],clip.generated_title||clip.title||t("新成片"));navigate(`/project/${project.id}/studio/${draft.id}`)})
  const genDone = workspace.generation?.status === 'completed' || workspace.generation?.status === 'partial'
  const [bannerDismissed, setBannerDismissed] = useState(false)
  const showMorePlatform = automatic && genDone && !bannerDismissed && !morePlatformBannerSeen()
  const usedFirstWindow = Boolean(workspace.plan?.overrides?.source_window)
  const [showFullImportTip, setShowFullImportTip] = useState(() => genDone && usedFirstWindow)
  useEffect(() => {
    if (!genDone) return
    if (usedFirstWindow) setShowFullImportTip(true)
  }, [genDone, workspace.generation?.status, usedFirstWindow])
  const alreadyPlatforms = workspace.generation?.requested_platforms || []
  const morePlatformId = suggestAnotherPlatform(getLocale(), alreadyPlatforms)
  const morePlatformLabel = morePlatformId === 'xiaohongshu' ? t('小红书')
    : morePlatformId === 'youtube_shorts' ? 'Shorts'
    : platformLabel(morePlatformId)
  const startAnotherPlatform = () => {
    dismissMorePlatformBanner()
    setBannerDismissed(true)
    if (!project.source_url) {
      setRemaking(true)
      return
    }
    stashReuseImport({
      platforms: [morePlatformId],
      sourceUrl: project.source_url || undefined,
      sourceMeta: {
        source_url: project.source_url,
        source_file: project.source_file,
        video_path: project.video_path,
        project_id: project.id,
      },
    })
    navigate('/')
  }
  return <div className="studio-results">
    <FailureHint active={liveFailure} project={project} />
    {doneNote && <p className="studio-done-note" role="status">{t(noticeCopy(doneNote))}</p>}
    {showFullImportTip && genDone && usedFirstWindow && <div className="studio-more-platform" role="status" data-testid="t2-full-import-tip">
      <p className="studio-muted">{t('配置没问题，可以重新导入全片')}</p>
      <div className="studio-actions">
        <Btn size="sm" variant="cta" onClick={() => { setShowFullImportTip(false); navigate('/') }}>{t('重新导入全片')}</Btn>
        <Btn size="sm" variant="text" onClick={() => setShowFullImportTip(false)}>{t('知道了')}</Btn>
      </div>
    </div>}
    {remaking && <PlanEditDialog remake projectId={project.id} plan={workspace.plan} onClose={() => setRemaking(false)}
      onSubmitted={() => { setRemaking(false); refresh() }} />}
    {(managed || !!workspace.plan) && !automatic && workspace.analysis?.status === 'awaiting_confirmation' && workspace.plan &&
      <PlanSummary key={workspace.plan.id} projectId={project.id} plan={workspace.plan} remake
        status={workspace.analysis.status} onChanged={refresh} />}
    {automatic && workspace.generation?.skipped?.map(item=><p key={item.strategy_id} className="studio-output-hint">{t('未生成 {{platform}}：{{reason}}', { platform: platformLabel(item.strategy_id), reason: t(item.reason) })}</p>)}
    {!(workspace.analysis?.status==='awaiting_confirmation' && !variants.length && !workspace.drafts.length && !project.clips?.length && !project.collections?.length) && <Section title={t("剪辑与成片")} count={resultCount} description={[REPLAY_SOURCE_LABELS[workspace.import_source || (workspace.material_origin === 'obs' ? 'obs' : '')], automatic ? generationDescription : showDraftList ? (sourceDuration != null ? t('原素材 {{duration}}', { duration: fmtDuration(sourceDuration) }) : undefined) : visual ? t("候选已整理为可编辑草稿；导出完成后，才能下载带包装的视频。") : t("切片与合集都在这里，可以直接下载，也可以另存为成片草稿。")].filter(Boolean).join(' · ') || undefined} right={<div className="studio-actions">
        {automatic && workspace.plan?.content_type === 'gameplay' && <GameplayReview key={project.id} projectId={project.id} variants={variants} drafts={workspace.drafts} />}
        {managed && loaded && !automatic && (!hideLegacy || variants.length > 0) && workspace.analysis?.status !== 'awaiting_confirmation' &&
          <Btn size="sm" disabled={loading || workspace.analysis?.status === 'running'} onClick={() => { noteLegacy('plan_adjust'); setRemaking(true) }}>{t('再做一版')}</Btn>}
        {automatic && genDone && <Btn size="sm" disabled={loading || workspace.analysis?.status === 'running'} onClick={startAnotherPlatform}>{t('再做一版')}</Btn>}
        <Btn size="sm" onClick={()=>setHistory(true)}>{t("导出记录")}{completedExportCount > 0 && <> <span className="ac-mono">{completedExportCount}</span></>}</Btn>{!managed && !hideLegacy && <Btn size="sm" onClick={()=>{ noteLegacy('collection'); onCreateCollection() }}>{t("新建合集")}</Btn>}</div>}>
      {progress && <div className="ac-empty studio-processing">
        <div className="studio-progress" role="progressbar" aria-busy={progress.indeterminate || undefined} aria-valuenow={progress.indeterminate ? undefined : progress.percent} aria-valuemin={progress.indeterminate ? undefined : 0} aria-valuemax={progress.indeterminate ? undefined : 100} aria-valuetext={t(progress.label)}>
          <div className="studio-progress-track"><div className={`studio-progress-fill${progress.indeterminate ? ' studio-progress-fill--busy' : ''}`} style={progress.indeterminate ? undefined : { width: `${progress.percent}%` }} /></div>
          <div className="studio-progress-meta"><span>{t(progress.label)}</span>{!progress.indeterminate && <span className="ac-mono">{progress.percent}%</span>}</div>
        </div>
        <p className="studio-muted">{[
          progress.elapsedMinutes == null ? '' : progress.elapsedMinutes < 1 ? t('已进行不到 1 分钟') : t('已进行约 {{minutes}} 分钟', { minutes: progress.elapsedMinutes }),
          progress.etaOverrun ? t('比预期久，但仍在进行') : (progress.etaMin != null ? t('预计还需约 {{minutes}} 分钟', { minutes: progress.etaMin }) : ''),
          progress.modelBudget ? t('模型步骤最多约 20 分钟') : '',
          progress.approximate ? t('进度为估算，以阶段为准') : '',
        ].filter(Boolean).join(' · ')}</p>
        {progress.canLeave && <p className="studio-muted">{t('可以最小化到托盘，完成后会通知你')}</p>}
        {progress.detail && progress.detail !== progress.label && <p className="studio-muted">{t(progress.detail)}</p>}
        {workspace.analysis?.phase==='screening'&&!automatic?t("识别完成后，请确认要制作的类型；现在还不会开始剪辑。"):t("完成后草稿会出现在这里，可以先处理其他项目。")}
      </div>}
      {taskFailed && <div className="ac-failure-summary" role="alert">
        <b>{t(detailView.status)}</b>
        <p className="ac-failure-reason">{detailView.step ? <>{t(detailView.step)}：{t(detailView.reason)}</> : t(detailView.reason)}</p>
        <p className="ac-failure-outcome">{t(detailView.outcome, { count: preservedCount })}</p>
        {failureBilling && <p className="studio-billing">{t(failureBilling)}</p>}
        <div className="studio-actions">
          {escalateDiagnose && <Btn variant="cta" disabled={!!busy} onClick={() => setDiagnoseOpen(true)}>{t('看看哪里不对')}</Btn>}
          {detailView.primary && <Btn variant={escalateDiagnose ? undefined : 'cta'} disabled={!!busy} loading={busy==='retry-analysis'} onClick={() => {
            const action = detailView.primary
            if (!action || busy) return
            if (action.id === 'view_results') { document.querySelector('.studio-result-grid')?.scrollIntoView({ block: 'start' }); return }
            if (action.id === 'settings' || action.id === 'quota_check' || action.id === 'install_transcription') { navigate(settingsReturnUrl(action.destination || '/settings?section=analysis', project.id)); return }
            if (action.id === 'browser') { navigate(stageBrowserCookieRecovery(project.source_url)); return }
            if (action.id === 'change_video') { navigate('/'); return }
            if (action.id === 'switch_model') { setSwitchOpen(true); return }
            void act('retry-analysis', async () => { await studioApi.retry(project.id, { retry_kind: 'same' }) })
          }}>{t(resumePoint?.label || detailView.primary.label)}</Btn>}
          {rechargeUrl && <Btn disabled={!!busy} onClick={() => void openExternalLink(rechargeUrl)}>{t(rechargeLabel)}</Btn>}
          {resumePoint && <Btn disabled={!!busy} loading={busy==='retry-fresh'} onClick={() => void act('retry-fresh', async () => { await studioApi.retry(project.id, { retry_kind: 'same', fresh: true }) })}>{t('从头重做')}</Btn>}
        </div>
        {!escalateDiagnose && <div className="ac-failure-weak"><Btn variant="text" disabled={!!busy} onClick={() => setDiagnoseOpen(true)}>{t('看看哪里不对')}</Btn></div>}
      </div>}
      {error && <div className="ac-empty"><b>{t("成片草稿加载失败")}</b>{t(error)}<Btn onClick={refresh}>{t("重试")}</Btn></div>}
      <div className="ac-grid-3 studio-result-grid">{[...variants].sort((a, b) => Number(a.status === 'on_demand') - Number(b.status === 'on_demand')).map(variant => <OutputVariantCard key={variant.id} projectId={project.id} variant={variant} draft={variantDraft(variant.draft_id)} job={variantJob(variant.render_job_id)} billable={billable > 0} recommendation={{ recommended_template: workspace.generation?.recommended_template, accepted_recommendation: workspace.generation?.accepted_recommendation }} onRetry={()=>act(`retry-${variant.id}`, async()=>{await studioApi.retryOutputVariant(project.id, variant.id)})} onProduce={()=>act(`produce-${variant.id}`, async()=>{await studioApi.produceOutputVariant(project.id, variant.id, variant.strategy_id)})}/>)}{standaloneDrafts.map(d => <DraftResultCard key={d.id} projectId={project.id} draft={d} jobs={workspace.jobs}
        onEdit={()=>navigate(`/project/${project.id}/studio/${d.id}`)} allowExport={!hideLegacy} onExport={()=>{ noteLegacy('export_confirm'); setExporting(d) }} onHistory={()=>setHistory(true)} />)}{loaded && !automatic && !showDraftList && children}</div>
      {!loading&&!error&&!taskFailed&&workspace.generation?.status!=='rendering'&&!variants.length&&!workspace.drafts.length&&!project.clips?.length&&!project.collections?.length&&workspace.analysis?.status!=='running'&&!sourceUnusable&&!cookieRecovery&&<div className="ac-empty"><b>{t("暂时没有可用成片")}</b>{managed?t("可以重试，或修改制作方案。"):t("可调整最低评分后重试内容处理。")}</div>}
    </Section>}
    {showMorePlatform && genDone && <div className="studio-more-platform" role="status" data-testid="t1-more-platform">
      <p className="studio-muted">{morePlatformId === 'xiaohongshu' ? t('也可以再做一个小红书版本') : morePlatformId === 'youtube_shorts' ? t('也可以再做一个 Shorts 版本') : t('也可以再做一个{{platform}}版本', { platform: morePlatformLabel })}</p>
      <div className="studio-actions">
        <Btn size="sm" variant="cta" onClick={startAnotherPlatform}>{t('用同一素材再做一个')}</Btn>
        <Btn size="sm" variant="text" onClick={() => { dismissMorePlatformBanner(); setBannerDismissed(true) }}>{t('知道了')}</Btn>
      </div>
    </div>}
    {actionError&&<p className="studio-error" role="alert">{actionError}</p>}
    {(sourceCount > 0 || workspace.analysis?.coverage) && <details className="studio-details studio-source-details" open={workspace.events.length > 0 && !(variants.length || workspace.drafts.length)}><summary>{showDraftList ? t('来源片段') : visual ? t('高光片段') : t('来源片段')}{showDraftList && !!project.collections?.length && ` / ${t('合集')}`} <span className="ac-mono">{sourceCount}</span></summary>
      {workspace.analysis?.coverage && <p className="studio-muted">{workspace.analysis.coverage.note}{typeof workspace.analysis.coverage.sample_interval === 'number' ? ` ${t('全片初筛采样间隔约 {{seconds}} 秒。', { seconds: workspace.analysis.coverage.sample_interval.toFixed(1) })}` : ''}</p>}
      {workspace.events.map(e=><div className="studio-source-row" key={e.id}><div><b>{e.label}</b><p className="studio-muted">{t('{{start}}–{{end}} 秒', { start: e.start.toFixed(1), end: e.end.toFixed(1) })} · {e.evidence}</p></div><div className="studio-actions"><Btn size="sm" onClick={()=>setPreview(e)}>{t("查看原片")}</Btn><Btn size="sm" disabled={!!busy} loading={busy===e.id} onClick={()=>act(e.id,async()=>{const d=await studioApi.eventDraft(project.id,e.id);navigate(`/project/${project.id}/studio/${d.id}`)})}>{t("用于新成片")}</Btn></div></div>)}
      {showDraftList && loaded && legacyCount > 0 && <div className="ac-grid-3 studio-result-grid studio-source-grid">{children}</div>}
      {!showDraftList && project.clips?.map(c=><div className="studio-source-row" key={c.id}><div><b>{c.generated_title||c.title}</b><p className="studio-muted">{c.start_time}–{c.end_time}</p></div><Btn size="sm" disabled={!!busy} loading={busy===c.id} onClick={()=>createLegacy(c)}>{t("用于新成片")}</Btn></div>)}
    </details>}
    <details className="studio-details studio-source-details"><summary>{t("原素材")}</summary><video controls preload="none" className="studio-source-video" src={studioApi.source(project.id)}/></details>
    <ExportHistory projectId={project.id} jobs={workspace.jobs} variants={workspace.output_variants} open={history} onClose={()=>setHistory(false)}/>
    <Dialog open={!!preview} title={preview?.label||t("原片")} onClose={()=>setPreview(null)}>{preview&&<video key={preview.id} controls preload="metadata" className="studio-source-video" src={`${studioApi.source(project.id)}#t=${preview.start},${preview.end}`}/>}<p className="studio-muted">{preview?.evidence}</p></Dialog>
    <Dialog open={!!exporting} title={t("导出成片")} onClose={()=>!busy&&setExporting(null)} description={t("按当前草稿设置渲染，完成后在导出记录下载。")} footer={<div className="studio-actions"><Btn disabled={!!busy} onClick={()=>setExporting(null)}>{t("关闭")}</Btn><Btn variant="cta" disabled={!!busy} loading={busy==='export'} onClick={()=>exporting&&act('export',async()=>{await studioApi.export(project.id,exporting.id,exporting.revision, exporting);setExporting(null);setHistory(true)})}>{t("确认导出")}</Btn></div>}><p>{exporting?.title}</p><p className="studio-muted">{exporting?.aspect==='portrait'?t("9:16 竖屏"):exporting?.aspect==='landscape'?t("16:9 横屏"):t("原画幅")} · MP4 · 30 fps</p>{actionError&&<p className="studio-error">{actionError}</p>}</Dialog>
    <DiagnosePanel open={diagnoseOpen} onClose={() => setDiagnoseOpen(false)} info={{ ...resolvedCause, error: resolvedCause.error || workspace.analysis?.error }} reason={detailView.reason} onSettings={destination => navigate(settingsReturnUrl(destination, project.id))} />
    <SwitchModelDialog open={switchOpen} options={switchOptions} busy={busy==='retry-analysis'} onClose={() => setSwitchOpen(false)} onConfirm={choice => { setSwitchOpen(false); void act('retry-analysis', async () => { await switchModelAndRetry(choice) }) }} />
  </div>
}
