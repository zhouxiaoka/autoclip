import { ReactNode, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Project, Clip } from '../../store/useProjectStore'
import { Btn, Section, Dialog, fmtDuration } from '../../ui'
import { studioApi, errorText } from './api'
import { useWorkspace } from './useWorkspace'
import { draftDuration, Scene, Draft, languages } from './types'
import ExportHistory from './ExportHistory'

import './studio.css'

export default function StudioResults({ project, children, onCreateCollection, onReload }: { project: Project; children: ReactNode; onCreateCollection: () => void; onReload: () => void }) {
  const navigate = useNavigate()
  const {workspace,error,loading,refresh} = useWorkspace(project.id)
  const [history, setHistory] = useState(false)
  const [busy,setBusy] = useState('')
  const [actionError,setActionError] = useState('')
  const [preview,setPreview] = useState<Scene|null>(null)
  const [exporting,setExporting] = useState<Draft|null>(null)
  const goal = project.settings?.creative?.goal || project.processing_config?.creative?.goal || 'content'
  const visual = goal !== 'content'
  const sourceDuration=workspace.plan?.source_duration ?? workspace.analysis?.coverage?.duration
  const managed = visual || !!project.settings?.smart_import || !!project.processing_config?.smart_import
  useEffect(()=>{if(workspace.analysis && workspace.analysis.status!=='running' && project.status!=='completed') onReload()},[workspace.analysis?.status])
  const act = async (key: string, fn:()=>Promise<void>) => {setBusy(key);setActionError('');try{await fn();refresh()}catch(e){setActionError(errorText(e))}finally{setBusy('')}}
  const createLegacy = (clip: Clip) => act(clip.id, async()=>{const draft=await studioApi.create(project.id,[clip.id],clip.generated_title||clip.title||'新成片');navigate(`/project/${project.id}/studio/${draft.id}`)})
  return <>
    {managed && <div className="studio-row"><span className="studio-muted">{sourceDuration!=null?`原素材 ${fmtDuration(sourceDuration)} · `:''}{workspace.analysis?.status==='awaiting_confirmation'?'新制作方案待确认，已有结果保留。':'制作结果与编辑'}</span><Btn size="sm" disabled={workspace.analysis?.status==='running'} onClick={()=>navigate(`/import/${project.id}`)}>{workspace.analysis?.status==='awaiting_confirmation'?'继续确认方案':'调整制作方案'}</Btn></div>}
    {!(workspace.analysis?.status==='awaiting_confirmation' && !workspace.drafts.length && !project.clips?.length && !project.collections?.length) && <Section title="你的成片" count={workspace.drafts.length+(project.clips?.length||0)+(project.collections?.length||0)} description={visual?'从真实画面中寻找精彩，选喜欢的成片继续修改或导出。':'切片与合集都在这里，可以直接下载，也可以另存为成片草稿。'} right={<div className="studio-actions"><Btn size="sm" onClick={()=>setHistory(true)}>导出记录</Btn>{!managed&&<Btn size="sm" onClick={onCreateCollection}>新建合集</Btn>}</div>}>
      {workspace.analysis?.status==='running' && <div className="ac-empty studio-processing"><b><span className="spin"/> {workspace.analysis.message||'分析画面中'}</b>{workspace.analysis.phase==='screening'?'识别完成后，请确认要制作的类型；现在还不会开始剪辑。':'完成后草稿会出现在这里，可以先处理其他项目。'}</div>}
      {workspace.analysis?.status==='failed' && <div className="ac-empty"><b>这次制作未完成</b><span className="studio-error">{workspace.analysis.error}</span><Btn onClick={()=>navigate('/settings')}>模型设置</Btn></div>}
      {error && <div className="ac-empty"><b>成片草稿加载失败</b>{error}<Btn onClick={refresh}>重试</Btn></div>}
      <div className="ac-grid-3 studio-result-grid">{workspace.drafts.map(d=><article className="ac-card" key={d.id}><button className="ac-card-thumb studio-thumb" onClick={()=>navigate(`/project/${project.id}/studio/${d.id}`)} aria-label={`预览 ${d.title}`}><video muted preload="metadata" src={`${studioApi.source(project.id)}#t=${d.scenes[0].start}`} /><span className="play">▷</span><span className="ac-tag ac-tag--tl">{d.origin==='visual-promo'?'推广成片':d.origin==='visual-highlight'?'精彩高光':'成片草稿'}</span><span className="ac-tag ac-tag--br">{fmtDuration(draftDuration(d))}</span></button><div className="ac-card-body"><h2 className="ac-card-title">{d.title}</h2><div className="ac-card-desc">{d.hook||d.scenes[0].evidence||'保留原声与完整事件'}</div><div className="ac-card-foot"><span className="meta">{languages.find(l => l.value === d.language)?.label} · V{d.revision} · {d.scenes.length} 段</span><div className="ac-card-actions"><Btn variant="text" onClick={()=>navigate(`/project/${project.id}/studio/${d.id}`)}>预览与修改</Btn><Btn variant="text" onClick={()=>setExporting(d)}>导出</Btn></div></div></div></article>)}{children}</div>
      {!loading&&!error&&!workspace.drafts.length&&!project.clips?.length&&!project.collections?.length&&workspace.analysis?.status!=='running'&&<div className="ac-empty"><b>暂时没有可用成片</b>{managed?'可以重试，或修改制作方案。':'可调整最低评分后重试内容处理。'}</div>}
    </Section>}
    {actionError&&<p className="studio-error" role="alert">{actionError}</p>}
    <details className="studio-details studio-source-details"><summary>{visual?'高光片段':'来源片段'} <span className="ac-mono">{workspace.events.length+(project.clips?.length||0)}</span> · 需要换镜头时再选</summary>
      {workspace.analysis?.coverage && <p className="studio-muted">{workspace.analysis.coverage.note} 全片初筛采样间隔约 {workspace.analysis.coverage.sample_interval.toFixed(1)} 秒。</p>}
      {workspace.events.map(e=><div className="studio-source-row" key={e.id}><div><b>{e.label}</b><p className="studio-muted">{e.start.toFixed(1)}–{e.end.toFixed(1)} 秒 · {e.evidence}</p></div><div className="studio-actions"><Btn size="sm" onClick={()=>setPreview(e)}>查看原片</Btn><Btn size="sm" disabled={!!busy} loading={busy===e.id} onClick={()=>act(e.id,async()=>{const d=await studioApi.eventDraft(project.id,e.id);navigate(`/project/${project.id}/studio/${d.id}`)})}>用于新成片</Btn></div></div>)}
      {project.clips?.map(c=><div className="studio-source-row" key={c.id}><div><b>{c.generated_title||c.title}</b><p className="studio-muted">{c.start_time}–{c.end_time}</p></div><Btn size="sm" disabled={!!busy} loading={busy===c.id} onClick={()=>createLegacy(c)}>用于新成片</Btn></div>)}
    </details>
    <details className="studio-details studio-source-details"><summary>原素材</summary><video controls preload="none" className="studio-source-video" src={studioApi.source(project.id)}/></details>
    <ExportHistory projectId={project.id} jobs={workspace.jobs} open={history} onClose={()=>setHistory(false)}/>
    <Dialog open={!!preview} title={preview?.label||'原片'} onClose={()=>setPreview(null)}>{preview&&<video key={preview.id} controls preload="metadata" className="studio-source-video" src={`${studioApi.source(project.id)}#t=${preview.start},${preview.end}`}/>}<p className="studio-muted">{preview?.evidence}</p></Dialog>
    <Dialog open={!!exporting} title="导出成片" onClose={()=>!busy&&setExporting(null)} description="按当前草稿设置渲染，完成后在导出记录下载。" footer={<div className="studio-actions"><Btn disabled={!!busy} onClick={()=>setExporting(null)}>关闭</Btn><Btn variant="cta" disabled={!!busy} loading={busy==='export'} onClick={()=>exporting&&act('export',async()=>{await studioApi.export(project.id,exporting.id,exporting.revision);setExporting(null);setHistory(true)})}>确认导出</Btn></div>}><p>{exporting?.title}</p><p className="studio-muted">{exporting?.aspect==='portrait'?'9:16 竖屏':exporting?.aspect==='landscape'?'16:9 横屏':'原画幅'} · MP4 · 30 fps</p>{actionError&&<p className="studio-error">{actionError}</p>}</Dialog>
  </>
}
