import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Btn, Dialog, ProgressLine, Row, fmtDuration } from '../../ui'
import { studioApi, errorText } from './api'
import { useWorkspace } from './useWorkspace'
import { Draft, Scene, languages, draftDuration, draftError, moveScene, applyCandidate, portraitDesign } from './types'
import CandidatePicker from './CandidatePicker'
import TitleArtwork from './TitleArtwork'
import DraftVariantDialog from './DraftVariantDialog'
import './studio.css'

export default function StudioEditor() {
  const { id, draftId } = useParams()
  return <Editor key={`${id}:${draftId}`} projectId={id!} draftId={draftId!} />
}
function Editor({ projectId, draftId }: { projectId: string; draftId: string }) {
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
  const [suggestion, setSuggestion] = useState<Draft | null>(null)
  const [undo, setUndo] = useState<Draft | null>(null)
  const video = useRef<HTMLVideoElement>(null)
  const localKey = `autoclip.studio.${projectId}.${draftId}`
  const dirty = !!draft && JSON.stringify(draft) !== saved
  const artworkStyle = ['comic','neon','arena','editorial','pixel','frosted'].includes(draft?.title_style || '')
  const scene = draft?.scenes[selected] || draft?.scenes[0]
  const jobs = workspace.jobs.filter(j => j.draft_id === draftId)
  const currentJob = draft && !dirty ? jobs.find(j => j.revision === draft.revision) : undefined
  const active = jobs.find(j => j.status === 'queued' || j.status === 'running')

  useEffect(() => {
    if (draft) return
    const server = workspace.drafts.find(d => d.id === draftId)
    if (!server) return
    setSaved(JSON.stringify(server))
    try {
      const cached = JSON.parse(localStorage.getItem(localKey) || 'null') as Draft | null
      if (cached && cached.revision === server.revision && cached.id === server.id && !draftError(cached)) {
        setDraft(cached); setNotice('已恢复本机暂存的修改，请保存后导出'); return
      }
    } catch { /* A damaged local cache must never hide the server draft. */ }
    setDraft(server)
  }, [workspace, draftId, draft])
  useEffect(() => {
    if (!draft) return
    try { if (dirty) localStorage.setItem(localKey, JSON.stringify(draft)); else localStorage.removeItem(localKey) } catch { setNotice('本机暂存不可用，请及时保存草稿') }
    const warn = (e: BeforeUnloadEvent) => { if (dirty) { e.preventDefault(); e.returnValue = '' } }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [draft, dirty])
  useEffect(() => {
    if (video.current && scene && !showRendered) video.current.currentTime = scene.start
  }, [scene?.id, scene?.start, showRendered])
  const patch = (changes: Partial<Draft>) => { if (draft) { setDraft({...draft, ...changes}); setShowRendered(false); setError('') } }
  const save = async (): Promise<Draft> => {
    if (!draft) throw new Error('草稿不存在')
    const invalid = draftError(draft, sourceDuration)
    if (invalid) throw new Error(invalid)
    if (!dirty) return draft
    const result = await studioApi.save(projectId, draft)
    setDraft(result); setSaved(JSON.stringify(result)); setNotice('草稿已保存'); refresh()
    return result
  }
  const perform = async (kind: string, action: () => Promise<void>) => {
    setBusy(kind); setError('')
    try { await action() } catch (e) { setError(errorText(e)) } finally { setBusy('') }
  }
  const render = async () => {
    await perform('render', async () => {
      const savedDraft = await save()
      await studioApi.export(projectId, savedDraft.id, savedDraft.revision)
      refresh(); setNotice('渲染已开始，可以离开页面，之后在导出记录查看')
    })
  }
  const rewrite = async () => {
    if (!draft || !instruction.trim()) return
    await perform('rewrite', async () => setSuggestion(await studioApi.rewrite(projectId, draft, instruction.trim())))
  }
  if (!draft) return <div className="ac-page"><button className="ac-back" onClick={() => navigate(`/project/${projectId}`)}>‹ 返回项目</button><div className="ac-empty"><b>{loading ? '加载成片草稿…' : '无法打开草稿'}</b>{loadError || (!loading && '草稿不存在或已移除')}<Btn onClick={refresh}>重试</Btn></div></div>
  const previewUrl = currentJob?.status === 'completed' ? studioApi.video(projectId, currentJob.job_id) : ''
  const updateScene = (i: number, update: Partial<Scene>) => patch({ scenes: draft.scenes.map((s, index) => index === i ? {...s,...update} : s) })
  return <div className="ac-page studio-editor-page">
    <button className="ac-back" onClick={() => navigate(`/project/${projectId}`)}>‹ 返回项目</button>
    <header className="studio-row studio-editor-head"><div><h1 className="ac-title">{draft.title}</h1><span className="studio-muted">{dirty ? '有修改未保存 · 本机暂存' : '草稿已保存'} · V{draft.revision} · {fmtDuration(draftDuration(draft))}</span></div><div className="studio-actions"><Btn disabled={!!busy} onClick={() => setShowVariant(true)}>另存为新版本</Btn><Btn disabled={!!busy || !dirty} loading={busy==='save'} onClick={() => perform('save', async () => {await save()})}>保存草稿</Btn><Btn variant="cta" disabled={!!busy} onClick={() => setShowExport(true)}>导出成片</Btn></div></header>
    {loadError && <p className="studio-error">任务状态暂时无法更新：{loadError}</p>}
    <fieldset disabled={!!busy} className="studio-fieldset">
      <div className="studio-editor-grid"><section><div className={`studio-stage studio-stage--${draft.aspect}`}>
        <div className="studio-video-frame" style={{aspectRatio: draft.aspect==='portrait'?'9/16':draft.aspect==='landscape'?'16/9':undefined}}>
          <video ref={video} controls preload="metadata" muted={!draft.original_audio} src={showRendered && previewUrl ? previewUrl : studioApi.source(projectId)} style={{objectFit: showRendered || draft.layout!=='crop'?'contain':'cover', objectPosition:`${(draft.crop_x ?? .5)*100}% 50%`}} onLoadedMetadata={() => { if(video.current && scene && !showRendered) { setSourceDuration(video.current.duration); video.current.currentTime=scene.start } }} onTimeUpdate={() => {const v=video.current; if(v && scene && !showRendered && v.currentTime>=scene.end) {v.pause();v.currentTime=scene.start}}} />
          {!showRendered && selected===0 && draft.hook && !artworkStyle && <div className={`studio-hook studio-hook--${draft.title_style || 'plain'}`}>{draft.hook}</div>}
          {!showRendered && selected===0 && draft.hook && artworkStyle && <TitleArtwork projectId={projectId} draft={draft}/>}
        </div>
      </div><div className="studio-row studio-preview-foot"><span className="studio-muted">{showRendered?'实际渲染结果':'原片预览 · 字幕、翻译以渲染结果为准'}</span>{previewUrl ? <Btn size="sm" onClick={() => setShowRendered(!showRendered)}>{showRendered?'查看原片':'播放成片'}</Btn> : <Btn size="sm" disabled={!!active} onClick={render}>{active?'正在渲染':'渲染预览'}</Btn>}</div></section>
      <aside className="studio-edit-panel"><h2>改到满意，就导出。</h2><Btn size="sm" onClick={() => patch(portraitDesign(draft))}>应用竖屏推荐</Btn><label className="studio-field">成片名称<input maxLength={200} value={draft.title} onChange={e => patch({title:e.target.value})} /></label><label className="studio-field">开头文字<textarea maxLength={120} value={draft.hook} placeholder="可留空；在开头约 4 秒显示" onChange={e => patch({hook:e.target.value})} /></label>
        <div className="studio-field"><span>标题模板</span><div className="studio-template-options">{([{value:'comic',label:'漫画冲击'},{value:'neon',label:'荧光挑战'},{value:'arena',label:'竞技斜切'},{value:'pixel',label:'像素街机'},{value:'editorial',label:'极简大字'},{value:'frosted',label:'磨砂字幕卡'},{value:'impact',label:'高能大字'},{value:'card',label:'简洁标题卡'},{value:'plain',label:'基础文字'}] as const).map(t=><button type="button" key={t.value} className={`studio-template studio-template--${t.value} ${['comic','neon','arena','editorial','pixel','frosted'].includes(t.value)?'studio-template--art':''}`} aria-pressed={(draft.title_style || 'plain') === t.value} onClick={()=>patch({title_style:t.value,title_template_version:t.value==='comic'?4:3,title_accent:null})}>{['comic','neon','arena','editorial','pixel','frosted'].includes(t.value)&&<img src={studioApi.titleThumbnail(t.value,t.value==='comic'?4:3)} alt=""/>}<span>{t.label}</span></button>)}</div></div>{artworkStyle && <details className="studio-details"><summary>调整文字样式</summary>{!['pixel','frosted'].includes(draft.title_style||'') && <label className="studio-field">样式版本<select aria-label="样式版本" value={draft.title_template_version??1} onChange={e=>patch({title_template_version:Number(e.target.value) as 1|2|3|4|5})}>{draft.title_style==='comic' && <><option value={5}>冲击加强版</option><option value={4}>设计校准版</option></>}<option value={3}>光泽版</option><option value={2}>加强版</option>{draft.title_style!=='editorial' && <option value={1}>原版</option>}</select></label>}<label className="studio-field">强调色<input type="color" aria-label="标题强调色" value={draft.title_accent || (draft.title_style==='comic'?'#ffe52d':draft.title_style==='neon'?'#ccff00':draft.title_style==='editorial'?'#ff4826':draft.title_style==='pixel'?'#ed327c':draft.title_style==='frosted'?'#00e6dc':'#dfff00')} onChange={e=>patch({title_accent:e.target.value})}/></label><label className="studio-field">文字大小<input type="range" aria-label="文字大小" min=".75" max="1.2" step=".05" value={draft.title_scale??1} onChange={e=>patch({title_scale:Number(e.target.value)})}/></label><label className="studio-field">文字位置<input type="range" aria-label="文字位置" min=".06" max=".70" step=".01" value={draft.title_y??.12} onChange={e=>patch({title_y:Number(e.target.value)})}/></label>{!['pixel','frosted'].includes(draft.title_style||'') && <label><input type="checkbox" checked={draft.title_motion??true} onChange={e=>patch({title_motion:e.target.checked})}/> 开启入场动效</label>}<p className="studio-muted">预览使用实际文字图层。翻译与入场动效以渲染结果为准；支持手动换行。</p></details>}<label className="studio-field">输出文字语言<select value={draft.language} onChange={e => patch({language:e.target.value as Draft['language']})}>{languages.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}</select></label>
        <p className="studio-muted">选择翻译语言后，渲染时会翻译开头文字与所选原字幕。</p>
        <Row label="字幕"><label><input type="checkbox" checked={draft.subtitles} onChange={e=>patch({subtitles:e.target.checked})} /> 烧录原字幕</label></Row><Row label="声音"><label><input type="checkbox" checked={draft.original_audio} onChange={e=>patch({original_audio:e.target.checked})} /> 保留原声</label></Row>
        <details className="studio-details"><summary>画面设置</summary><label className="studio-field">画幅<select value={draft.aspect} onChange={e=>patch({aspect:e.target.value as Draft['aspect'], ...(e.target.value==='portrait'?{layout:'crop' as const}:{})})}><option value="original">原画幅</option><option value="portrait">9:16 竖屏</option><option value="landscape">16:9 横屏</option></select></label><label className="studio-field">构图<select value={draft.layout} onChange={e=>patch({layout:e.target.value as Draft['layout']})}><option value="fit">完整画面 · 留边</option><option value="blur">完整画面 · 模糊背景</option><option value="crop">满屏取景</option></select></label>{draft.layout==='crop' && <label className="studio-field">取景位置 · 左右移动<input aria-label="取景位置" type="range" min="0" max="1" step=".01" value={draft.crop_x ?? .5} onChange={e=>patch({crop_x:Number(e.target.value)})}/></label>}<p className="studio-muted">{draft.layout==='crop'?'主体铺满画面。左右调整取景，检查角色、障碍与 HUD 是否完整。':draft.aspect==='portrait'?'当前保留横屏全画面，会产生留边；想铺满竖屏请选择「满屏取景」。':'保留原画面构图。'}</p></details>
      </aside></div>
      <div className="studio-prompt"><input aria-label="文案修改要求" placeholder="告诉 AI 怎么改文案，例如：开头改成一个简短的问题" value={instruction} onChange={e=>setInstruction(e.target.value)} /><Btn variant="cta" loading={busy==='rewrite'} disabled={!instruction.trim()} onClick={rewrite}>改一版文案</Btn></div>
      {undo && <Btn variant="text" onClick={()=>{setDraft({...undo, revision:draft.revision});setUndo(null);setShowRendered(false)}}>撤销上次修改</Btn>}
      <details className="studio-details studio-source-details"><summary>调整镜头 <span className="ac-mono">{draft.scenes.length}</span> · 顺序与起止点</summary>
        <Btn size="sm" disabled={draft.scenes.length >= 30} onClick={() => setPicker('append')}>追加镜头</Btn>
        {draft.scenes.map((s,i)=><div className="studio-scene-row" key={s.id}><Btn size="sm" onClick={()=>{setSelected(i);setShowRendered(false)}}>{i+1}. {s.label}</Btn><label>起点（秒）<input type="number" min={0} step={.1} value={s.start} onChange={e=>updateScene(i,{start:Number(e.target.value)})}/></label><label>终点（秒）<input type="number" min={0} step={.1} value={s.end} onChange={e=>updateScene(i,{end:Number(e.target.value)})}/></label><div className="studio-actions"><Btn size="sm" onClick={() => setPicker(i)}>替换</Btn><Btn size="sm" disabled={i===0} onClick={()=>patch({scenes:moveScene(draft,i,-1).scenes})}>上移</Btn><Btn size="sm" disabled={i===draft.scenes.length-1} onClick={()=>patch({scenes:moveScene(draft,i,1).scenes})}>下移</Btn><Btn size="sm" disabled={draft.scenes.length===1} onClick={()=>{patch({scenes:draft.scenes.filter((_,index)=>index!==i)});setSelected(0)}}>移除</Btn></div></div>)}
      </details>
    </fieldset>
    {active && <div className="studio-render-state"><ProgressLine percent={active.percent}/><span className="studio-muted">{active.status==='queued'?'等待渲染':'渲染成片'} · {active.percent}%</span></div>}
    {currentJob?.status==='failed' && <p className="studio-error" role="alert">{currentJob.error}</p>}
    {currentJob?.result?.warnings.map(w=><p className="studio-muted" key={w}>{w}</p>)}
    {error && <p className="studio-error" role="alert">{error}</p>}<p className="studio-muted" role="status">{notice}</p>
    {picker !== null && <CandidatePicker projectId={projectId} mode={picker === 'append' ? 'append' : 'replace'} onClose={() => setPicker(null)} onChoose={candidate => {
      try {
        const next = applyCandidate(draft, candidate, picker, crypto.randomUUID())
        setUndo(draft); patch({ scenes: next.scenes }); setSelected(picker === 'append' ? draft.scenes.length : picker)
        setPicker(null); setNotice('镜头已更新，请保存后重新渲染。换镜头后请核对开头文案是否仍符合画面。')
      } catch(e) { setPicker(null); setError(errorText(e)) }
    }} />}
    <DraftVariantDialog open={showVariant} projectId={projectId} draft={draft} onClose={() => setShowVariant(false)} onCreated={created => {
      try { localStorage.removeItem(localKey) } catch { /* The new server draft is already durable. */ }
      navigate(`/project/${projectId}/studio/${created.id}`)
    }} />
    <Dialog open={!!suggestion} onClose={()=>setSuggestion(null)} title="查看文案修改" description="确认后应用到当前草稿，镜头与声音保持原设置。" footer={<div className="studio-actions"><Btn onClick={()=>setSuggestion(null)}>保留原稿</Btn><Btn variant="cta" onClick={()=>{setUndo(draft);setDraft(suggestion);setSuggestion(null);setShowRendered(false)}}>应用修改</Btn></div>}><p>{suggestion?.title}</p><p>{suggestion?.hook || '无开头文字'}</p></Dialog>
    <Dialog open={showExport} onClose={()=>!busy && setShowExport(false)} title="导出成片" description="保存当前修改并渲染；已有输出会保留在导出记录。" footer={<div className="studio-actions"><Btn disabled={!!busy} onClick={()=>setShowExport(false)}>关闭</Btn>{previewUrl ? <a className="ac-btn ac-btn--cta" href={studioApi.video(projectId,currentJob!.job_id,true)} download>下载成片</a> : <Btn variant="cta" loading={busy==='render'||!!active} disabled={!!active} onClick={render}>确认导出</Btn>}</div>}>
      <Row label="成片">{draft.title}</Row><Row label="格式">MP4 · 30 fps</Row><Row label="画幅">{draft.aspect==='portrait'?'1080 × 1920':draft.aspect==='landscape'?'1920 × 1080':'保持原尺寸'}</Row><Row label="文字语言">{languages.find(l=>l.value===draft.language)?.label}</Row>
      {active && <ProgressLine percent={active.percent}/>}<p className="studio-muted">{previewUrl?'当前版本已渲染完成，可以直接下载。':'任务在后台继续，关闭面板不会取消渲染。'}</p>{error && <p className="studio-error">{error}</p>}{currentJob?.status==='failed'&&<p className="studio-error">{currentJob.error}</p>}
    </Dialog>
  </div>
}
