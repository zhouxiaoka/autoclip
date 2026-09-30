import { useTranslation } from 'react-i18next'
import { t } from '../../i18n'
import StudioDownloadLink from './StudioDownloadLink'
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Btn, Dialog, ProgressLine, Row, fmtDuration } from '../../ui'
import { studioApi, errorText, type SourcePreview } from './api'
import { useWorkspace } from './useWorkspace'
import PlayerBar from './PlayerBar'
import { CropPoint, Draft, Scene, SubtitleCue, languages, draftDuration, draftError, moveScene, applyCandidate, portraitDesign, cropAt, frameModeAt, patchShot } from './types'
import CandidatePicker from './CandidatePicker'
import TitleArtwork from './TitleArtwork'
import DraftVariantDialog from './DraftVariantDialog'
import { titlePresets, isArtworkStyle } from './titlePresets'
import DraftSettingsPanel, { type FramingState } from './DraftSettingsPanel'
import { draftExportState } from './draftExportState'
import './studio.css'

export default function StudioEditor() {
  const { id, draftId } = useParams()
  return <Editor key={`${id}:${draftId}`} projectId={id!} draftId={draftId!} />
}
function Editor({ projectId, draftId }: { projectId: string; draftId: string }) {
  useTranslation()
  const navigate = useNavigate()
  const { workspace, error: loadError, loading, refresh } = useWorkspace(projectId)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [saved, setSaved] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [instruction, setInstruction] = useState('')
  const [selected, setSelected] = useState(0)
  const [picker, setPicker] = useState<number | 'append' | null>(null)
  const [sourceDuration, setSourceDuration] = useState<number>()
  const [showVariant, setShowVariant] = useState(false)
  const [showExport, setShowExport] = useState(false)
  const [showRendered, setShowRendered] = useState(false)
  const [playbackError, setPlaybackError] = useState(false)
  const [sourcePreview, setSourcePreview] = useState<SourcePreview>({status: 'idle'})
  const [cues, setCues] = useState<SubtitleCue[]>([])
  const [currentTime, setCurrentTime] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [muted, setMuted] = useState(false)
  const [renderedDuration, setRenderedDuration] = useState(0)
  const [framing, setFraming] = useState<FramingState>({ busy: false })
  useEffect(() => {
    const controller = new AbortController()
    studioApi.subtitles(projectId, controller.signal).then(v => setCues(v.cues)).catch(() => setCues([]))
    studioApi.framingStatus().then(status => setFraming(f => ({ ...f, status }))).catch(() => undefined)
    return () => controller.abort()
  }, [projectId])
  useEffect(() => {
    if (framing.status?.status !== 'installing') return
    const timer = window.setInterval(() => {
      studioApi.framingStatus().then(status => setFraming(f => ({ ...f, status }))).catch(() => undefined)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [framing.status?.status])
  useEffect(() => {
    if (!['queued', 'running'].includes(sourcePreview.status)) return
    let cancelled = false
    const timer = window.setInterval(() => {
      studioApi.previewStatus(projectId).then(state => {
        if (cancelled) return
        setSourcePreview(state)
        if (state.status === 'completed') setPlaybackError(false)
      }).catch(error => { if (!cancelled) setSourcePreview({status:'failed', error:errorText(error)}) })
    }, 1500)
    return () => { cancelled = true; window.clearInterval(timer) }
  }, [projectId, sourcePreview.status])
  const preparePreview = async () => {
    setSourcePreview({status:'queued'})
    try {
      const state = await studioApi.preparePreview(projectId)
      setSourcePreview(state)
      if (state.status === 'completed') setPlaybackError(false)
    } catch(error) { setSourcePreview({status:'failed', error:errorText(error)}) }
  }

  /** Centre every scene's crop window on the speaker; scenes without a face keep their value. */
  const autoFrame = async (target?: Draft, trigger: 'auto' | 'manual' | 'portrait_preset' = 'manual') => {
    const base = target || draft
    if (!base || framing.status?.status !== 'installed') return
    setFraming(f => ({ ...f, busy: true, error: undefined }))
    try {
      const result = await studioApi.autoFrame(projectId, base, trigger)
      const found = new Map(result.scenes.filter(s => s.crop_x !== null).map(s => [s.id, s]))
      setDraft(current => current ? { ...current, scenes: current.scenes.map(sc => { const f = found.get(sc.id); return f ? { ...sc, crop_x: f.crop_x, crop_track: f.crop_track, framing_source: 'auto' as const, framing_adjusted: false } : sc }) } : current)
      setShowRendered(false)
      setFraming(f => ({ ...f, busy: false, result: { framed: found.size, total: result.scenes.length, shots: result.scenes.reduce((n, s) => n + (s.crop_track?.length ?? 0), 0), fit: result.scenes.reduce((n, s) => n + s.fit_shots, 0) } }))
    } catch (e) { setFraming(f => ({ ...f, busy: false, error: t(errorText(e)) })) }
  }
  const installFraming = async () => {
    try { const status = await studioApi.framingInstall(); setFraming(f => ({ ...f, status })) }
    catch (e) { setFraming(f => ({ ...f, error: t(errorText(e)) })) }
  }
  // Once the runtime lands (or the user switches to a cropped layout), frame automatically the first time.
  const cropping = !!draft && draft.aspect !== 'original' && draft.layout === 'crop'
  useEffect(() => {
    if (!cropping || framing.busy || framing.result || framing.status?.status !== 'installed') return
    if (draft?.scenes.some(s => s.crop_x != null || s.crop_track?.length)) return
    void autoFrame(undefined, 'auto')
  }, [cropping, framing.status?.status])
  /** Edit only the shot under the playhead; the rest of the scene's track stays as detected. */
  const setShot = (sceneId: string, changes: Partial<CropPoint>) => {
    if (draft) patch({ scenes: draft.scenes.map(sc => sc.id === sceneId ? { ...patchShot(sc, currentTime, changes, draft.crop_x ?? .5), framing_source: sc.framing_source || 'manual', framing_adjusted: true } : sc) })
  }
  const applyPortrait = () => {
    if (!draft) return
    const next = portraitDesign(draft)
    patch(next)
    setFraming(f => ({ ...f, result: undefined }))
    void autoFrame(next, 'portrait_preset')
  }

  const [suggestion, setSuggestion] = useState<Draft | null>(null)
  const [undo, setUndo] = useState<Draft | null>(null)
  const video = useRef<HTMLVideoElement>(null)
  const localKey = `autoclip.studio.${projectId}.${draftId}`
  const dirty = !!draft && JSON.stringify(draft) !== saved
  const artworkStyle = isArtworkStyle(draft?.title_style)
  const scene = draft?.scenes[selected] || draft?.scenes[0]
  // The preview transport runs on the clip's own timeline: 0 = scene start (or rendered clip start).
  const playBase = showRendered ? 0 : scene?.start ?? 0
  const playLength = showRendered ? renderedDuration : scene ? scene.end - scene.start : 0
  const togglePlay = () => { const v = video.current; if (!v) return; if (v.paused) void v.play().catch(() => undefined); else v.pause() }
  const jobs = workspace.jobs.filter(j => j.draft_id === draftId)
  const exportState = draft ? draftExportState(draft, jobs) : undefined
  const currentJob = !dirty ? exportState?.completed || exportState?.failure : undefined
  const active = jobs.find(j => j.status === 'queued' || j.status === 'running')

  useEffect(() => {
    if (draft) return
    const server = workspace.drafts.find(d => d.id === draftId)
    if (!server) return
    setSaved(JSON.stringify(server))
    try {
      const cached = JSON.parse(localStorage.getItem(localKey) || 'null') as Draft | null
      if (cached && cached.revision === server.revision && cached.id === server.id && !draftError(cached)) {
        setDraft(cached); setNotice("已恢复本机暂存的修改，请保存后导出"); return
      }
    } catch { /* A damaged local cache must never hide the server draft. */ }
    setDraft(server)
  }, [workspace, draftId, draft])
  useEffect(() => {
    if (!draft) return
    try { if (dirty) localStorage.setItem(localKey, JSON.stringify(draft)); else localStorage.removeItem(localKey) } catch { setNotice("本机暂存不可用，请及时保存草稿") }
    const warn = (e: BeforeUnloadEvent) => { if (dirty) { e.preventDefault(); e.returnValue = '' } }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [draft, dirty])
  useEffect(() => {
    if (video.current && scene && !showRendered) video.current.currentTime = scene.start
  }, [scene?.id, scene?.start, showRendered])
  useEffect(() => { if (draft) setMuted(!draft.original_audio) }, [draft?.original_audio])
  const patch = (changes: Partial<Draft>) => { if (draft) { setDraft({...draft, ...changes}); setShowRendered(false); setError('') } }
  const save = async (): Promise<Draft> => {
    if (!draft) throw new Error(t("草稿不存在"))
    const invalid = draftError(draft, sourceDuration)
    if (invalid) throw new Error(t(invalid))
    if (!dirty) return draft
    const result = await studioApi.save(projectId, draft)
    setDraft(result); setSaved(JSON.stringify(result)); setNotice("草稿已保存"); refresh()
    return result
  }
  const perform = async (kind: string, action: () => Promise<void>) => {
    setBusy(kind); setError('')
    try { await action() } catch (e) { setError(t(errorText(e))) } finally { setBusy('') }
  }
  const render = async () => {
    await perform('render', async () => {
      const savedDraft = await save()
      await studioApi.export(projectId, savedDraft.id, savedDraft.revision, savedDraft)
      refresh(); setNotice("渲染已开始，可以离开页面，之后在导出记录查看")
    })
  }
  const rewrite = async () => {
    if (!draft || !instruction.trim()) return
    await perform('rewrite', async () => setSuggestion(await studioApi.rewrite(projectId, draft, instruction.trim())))
  }
  if (!draft) return <div className="ac-page"><button className="ac-back" onClick={() => navigate(`/project/${projectId}`)}>{t("‹ 返回项目")}</button><div className="ac-empty"><b>{loading ? t("加载成片草稿…") : t("无法打开草稿")}</b>{loadError || (!loading && t("草稿不存在或已移除"))}<Btn onClick={refresh}>{t("重试")}</Btn></div></div>
  const previewUrl = currentJob?.status === 'completed' ? studioApi.video(projectId, currentJob.job_id) : ''
  const activeCue = cues.find(c => c.start <= currentTime && currentTime < c.end)
  const updateScene = (i: number, update: Partial<Scene>) => patch({ scenes: draft.scenes.map((s, index) => index === i ? {...s,...update} : s) })
  return <div className="ac-page studio-editor-page">
    <button className="ac-back" onClick={() => navigate(`/project/${projectId}`)}>{t("‹ 返回项目")}</button>
    <header className="studio-row studio-editor-head"><div><h1 className="ac-title">{draft.title}</h1><span className="studio-muted">{dirty ? t("有修改未保存 · 本机暂存") : t("草稿已保存")} · V{draft.revision} · {fmtDuration(draftDuration(draft))}</span></div><div className="studio-actions"><Btn disabled={!!busy} onClick={() => setShowVariant(true)}>{t("另存为新版本")}</Btn><Btn disabled={!!busy || !dirty} loading={busy==='save'} onClick={() => perform('save', async () => {await save()})}>{t("保存草稿")}</Btn><Btn variant="cta" disabled={!!busy} onClick={() => setShowExport(true)}>{t("导出成片")}</Btn></div></header>
    {loadError && <p className="studio-error">{t("任务状态暂时无法更新：")}{t(loadError)}</p>}
    {!showRendered && (sourcePreview.status !== 'completed' || playbackError) && <details open={playbackError || ['queued', 'running', 'failed'].includes(sourcePreview.status)} className="studio-muted">
      <summary>{t('生成兼容预览')}</summary>
      <p>{t('原片无法播放时，可生成兼容预览；原片不变，不调用模型。')}</p>
      {sourcePreview.error && <p className="studio-error">{t(sourcePreview.error)}</p>}
      <Btn disabled={['queued', 'running'].includes(sourcePreview.status)} onClick={preparePreview}>{t(['queued', 'running'].includes(sourcePreview.status) ? '正在生成兼容预览，长视频可能需要几分钟…' : '生成兼容预览')}</Btn>
    </details>}
    <fieldset disabled={!!busy} className="studio-fieldset">
      <div className="studio-editor-grid"><section className="studio-editor-main"><div className="studio-editor-sticky"><div className={`studio-stage studio-stage--${draft.aspect}`}>
        <div className="studio-video-frame" style={{aspectRatio: draft.aspect==='portrait'?'9/16':draft.aspect==='landscape'?'16/9':undefined}}>
          <video ref={video} preload="metadata" playsInline muted={muted} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onError={() => setPlaybackError(true)} onLoadedData={() => setPlaybackError(false)} src={showRendered && previewUrl ? previewUrl : sourcePreview.status === 'completed' && sourcePreview.version ? studioApi.compatibleSource(projectId, sourcePreview.version) : studioApi.source(projectId)} style={{objectFit: showRendered || draft.layout!=='crop' || frameModeAt(scene, currentTime)==='fit'?'contain':'cover', objectPosition:`${cropAt(scene, currentTime, draft.crop_x ?? .5)*100}% 50%`}} onClick={togglePlay} onLoadedMetadata={() => { const v = video.current; if (!v) return; if (showRendered) setRenderedDuration(v.duration); else if (scene) { setSourceDuration(v.duration); v.currentTime = scene.start } }} onTimeUpdate={() => {const v=video.current; if(!v) return; setCurrentTime(v.currentTime); if(scene && !showRendered && (v.currentTime>=scene.end || v.currentTime<scene.start-.25)) {if(v.currentTime>=scene.end) v.pause(); v.currentTime=scene.start}}} />
          {!showRendered && draft.subtitles && activeCue && <div className={`studio-caption-overlay studio-caption studio-caption--${draft.subtitle_style || 'clean'}`}>{activeCue.text}</div>}
          {!showRendered && selected===0 && draft.hook && !artworkStyle && <div className={`studio-hook studio-hook--${draft.title_style || 'plain'}`}>{draft.hook}</div>}
          {!showRendered && selected===0 && draft.hook && artworkStyle && <TitleArtwork projectId={projectId} draft={draft}/>}
        </div>
        <PlayerBar offset={Math.max(0, Math.min(currentTime - playBase, playLength))} length={playLength} playing={playing} muted={muted}
          onToggle={togglePlay} onMute={() => setMuted(m => !m)}
          onSeek={offset => { const v = video.current; if (!v) return; v.currentTime = playBase + offset; setCurrentTime(v.currentTime) }} />
      </div><div className="studio-row studio-preview-foot"><span className="studio-muted">{showRendered?t("实际渲染结果"):t("原片预览 · 成片取 {{range}} · 字幕、翻译以渲染结果为准", { range: scene ? `${fmtDuration(scene.start)}–${fmtDuration(scene.end)}` : "" })}</span>{previewUrl ? <Btn size="sm" onClick={() => setShowRendered(!showRendered)}>{showRendered?t("查看原片"):t("播放成片")}</Btn> : <Btn size="sm" disabled={!!active} onClick={render}>{active?t("正在渲染"):t("渲染预览")}</Btn>}</div></div>
      <div className="studio-prompt"><input aria-label={t("文案修改要求")} placeholder={t("告诉 AI 怎么改文案，例如：开头改成一个简短的问题")} value={instruction} onChange={e=>setInstruction(e.target.value)} /><Btn variant="cta" loading={busy==='rewrite'} disabled={!instruction.trim()} onClick={rewrite}>{t("改一版文案")}</Btn></div>
      {undo && <Btn variant="text" onClick={()=>{setDraft({...undo, revision:draft.revision});setUndo(null);setShowRendered(false)}}>{t("撤销上次修改")}</Btn>}
      <details className="studio-details studio-source-details"><summary>{t("调整镜头")}{' '}<span className="ac-mono">{draft.scenes.length}</span>{' '}{t("· 顺序与起止点")}</summary>
        <Btn size="sm" disabled={draft.scenes.length >= 30} onClick={() => setPicker('append')}>{t("追加镜头")}</Btn>
        {draft.scenes.map((s,i)=><div className="studio-scene-row" key={s.id}><Btn size="sm" onClick={()=>{setSelected(i);setShowRendered(false)}}>{i+1}. {s.label}</Btn><label>{t("起点（秒）")}<input type="number" min={0} step={.1} value={s.start} onChange={e=>updateScene(i,{start:Number(e.target.value)})}/></label><label>{t("终点（秒）")}<input type="number" min={0} step={.1} value={s.end} onChange={e=>updateScene(i,{end:Number(e.target.value)})}/></label><div className="studio-actions"><Btn size="sm" onClick={() => setPicker(i)}>{t("替换")}</Btn><Btn size="sm" disabled={i===0} onClick={()=>patch({scenes:moveScene(draft,i,-1).scenes})}>{t("上移")}</Btn><Btn size="sm" disabled={i===draft.scenes.length-1} onClick={()=>patch({scenes:moveScene(draft,i,1).scenes})}>{t("下移")}</Btn><Btn size="sm" disabled={draft.scenes.length===1} onClick={()=>{patch({scenes:draft.scenes.filter((_,index)=>index!==i)});setSelected(0)}}>{t("移除")}</Btn></div></div>)}
      </details>
      </section>
      <DraftSettingsPanel draft={draft} patch={patch} scene={scene} currentTime={currentTime} onShot={setShot}
        framing={framing} onAutoFrame={() => void autoFrame()} onInstallFraming={() => void installFraming()} onPortrait={applyPortrait}
        coverHref={previewUrl && currentJob ? `/project/${projectId}/publish/studio-${currentJob.job_id}` : undefined}
        onOpenCover={href => navigate(href)} /></div>
    </fieldset>
    {active && <div className="studio-render-state"><ProgressLine percent={active.percent}/><span className="studio-muted">{active.status==='queued'?t("等待渲染"):t("渲染成片")} · {active.percent}%</span></div>}
    {currentJob?.status==='failed' && <p className="studio-error" role="alert">{t(currentJob.error || '')}</p>}
    {currentJob?.result?.warnings?.map(w=><p className="studio-muted" key={w}>{t(w)}</p>)}
    {error && <p className="studio-error" role="alert">{error}</p>}<p className="studio-muted" role="status">{t(notice)}</p>
    {picker !== null && <CandidatePicker projectId={projectId} mode={picker === 'append' ? 'append' : 'replace'} onClose={() => setPicker(null)} onChoose={candidate => {
      try {
        const next = applyCandidate(draft, candidate, picker, crypto.randomUUID())
        setUndo(draft); patch({ scenes: next.scenes }); setSelected(picker === 'append' ? draft.scenes.length : picker)
        setPicker(null); setNotice("镜头已更新，请保存后重新渲染。换镜头后请核对开头文案是否仍符合画面。")
      } catch(e) { setPicker(null); setError(t(errorText(e))) }
    }} />}
    <DraftVariantDialog open={showVariant} projectId={projectId} draft={draft} onClose={() => setShowVariant(false)} onCreated={created => {
      try { localStorage.removeItem(localKey) } catch { /* The new server draft is already durable. */ }
      navigate(`/project/${projectId}/studio/${created.id}`)
    }} />
    <Dialog open={!!suggestion} onClose={()=>setSuggestion(null)} title={t("查看文案修改")} description={t("确认后应用到当前草稿，镜头与声音保持原设置。")} footer={<div className="studio-actions"><Btn onClick={()=>setSuggestion(null)}>{t("保留原稿")}</Btn><Btn variant="cta" onClick={()=>{setUndo(draft);setDraft(suggestion);setSuggestion(null);setShowRendered(false)}}>{t("应用修改")}</Btn></div>}><p>{suggestion?.title}</p><p>{suggestion?.hook || t("无开头文字")}</p></Dialog>
    <Dialog open={showExport} onClose={()=>!busy && setShowExport(false)} title={t("导出成片")} description={t("保存当前修改并渲染；已有输出会保留在导出记录。")} footer={<div className="studio-actions"><Btn disabled={!!busy} onClick={()=>setShowExport(false)}>{t("关闭")}</Btn>{previewUrl && <Btn onClick={()=>navigate(`/project/${projectId}/publish/studio-${currentJob!.job_id}`)}>{t("发布这版成片")}</Btn>}{previewUrl ? <StudioDownloadLink className="ac-btn ac-btn--cta" projectId={projectId} jobId={currentJob!.job_id}/> : <Btn variant="cta" loading={busy==='render'||!!active} disabled={!!active} onClick={render}>{t("确认导出")}</Btn>}</div>}>
      <Row label={t("成片")}>{draft.title}</Row><Row label={t("格式")}>MP4 · 30 fps</Row><Row label={t("画幅")}>{draft.aspect==='portrait'?'1080 × 1920':draft.aspect==='landscape'?'1920 × 1080':t("保持原尺寸")}</Row><Row label={t("文字语言")}>{draft.language==='source' ? t('原语言') : languages.find(l=>l.value===draft.language)?.label}</Row>
      <Row label={t("片头标题")}>{draft.hook ? t(titlePresets.find(preset=>preset.value===(draft.title_style||'plain'))?.label ?? '') : t("无开头文字")}</Row><Row label={t("原声")}>{draft.original_audio?t("保留"):t("已关闭")}</Row><Row label={t("字幕")}>{draft.subtitles?t("字幕压进画面"):t("已关闭")}</Row><Row label={t("封面")} hint={t("渲染完成后，在发布页按平台生成带标题的封面。")}>{previewUrl && currentJob && <Btn size="sm" variant="text" onClick={()=>navigate(`/project/${projectId}/publish/studio-${currentJob.job_id}`)}>{t("去生成")}</Btn>}</Row>
      {currentJob?.status==='completed' && !!currentJob.result?.warnings?.length && <div role="status" className="studio-muted">{currentJob.result.warnings.map(w=><p key={w}>{t(w)}</p>)}</div>}
      {active && <ProgressLine percent={active.percent}/>}<p className="studio-muted">{previewUrl?t("当前版本已渲染完成，可以直接下载。"):t("任务在后台继续，关闭面板不会取消渲染。")}</p>{error && <p className="studio-error">{error}</p>}{currentJob?.status==='failed'&&<p className="studio-error">{t(currentJob.error || '')}</p>}
    </Dialog>
  </div>
}
