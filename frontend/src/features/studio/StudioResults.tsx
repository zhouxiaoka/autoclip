import { useTranslation } from 'react-i18next'
import { t } from '../../i18n'
import { ReactNode, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Project, Clip } from '../../store/useProjectStore'
import { Btn, Section, Dialog, fmtDuration } from '../../ui'
import { studioApi, errorText } from './api'
import { useWorkspace } from './useWorkspace'
import { Scene, Draft } from './types'
import ExportHistory from './ExportHistory'
import DraftResultCard from './DraftResultCard'

import './studio.css'

export default function StudioResults({ project, children, onCreateCollection, onReload }: { project: Project; children: ReactNode; onCreateCollection: () => void; onReload: () => void }) {
  useTranslation()
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
  const act = async (key: string, fn:()=>Promise<void>) => {setBusy(key);setActionError('');try{await fn();refresh()}catch(e){setActionError(t(errorText(e)))}finally{setBusy('')}}
  const createLegacy = (clip: Clip) => act(clip.id, async()=>{const draft=await studioApi.create(project.id,[clip.id],clip.generated_title||clip.title||t("新成片"));navigate(`/project/${project.id}/studio/${draft.id}`)})
  return <>
    {managed && <div className="studio-row"><span className="studio-muted">{sourceDuration!=null?`${t('原素材 {{duration}}', { duration: fmtDuration(sourceDuration) })} · `:''}{workspace.analysis?.status==='awaiting_confirmation'?t("新制作方案待确认，已有结果保留。"):t("制作结果与编辑")}</span><Btn size="sm" disabled={workspace.analysis?.status==='running'} onClick={()=>navigate(`/import/${project.id}`)}>{workspace.analysis?.status==='awaiting_confirmation'?t("继续确认方案"):t("调整制作方案")}</Btn></div>}
    {!(workspace.analysis?.status==='awaiting_confirmation' && !workspace.drafts.length && !project.clips?.length && !project.collections?.length) && <Section title={t("剪辑与成片")} count={workspace.drafts.length+(project.clips?.length||0)+(project.collections?.length||0)} description={visual?t("候选已整理为可编辑草稿；导出完成后，才能下载带包装的视频。"):t("切片与合集都在这里，可以直接下载，也可以另存为成片草稿。")} right={<div className="studio-actions"><Btn size="sm" onClick={()=>setHistory(true)}>{t("导出记录")}</Btn>{!managed&&<Btn size="sm" onClick={onCreateCollection}>{t("新建合集")}</Btn>}</div>}>
      {workspace.analysis?.status==='running' && <div className="ac-empty studio-processing"><b><span className="spin"/> {workspace.analysis.message||t("分析画面中")}</b>{workspace.analysis.phase==='screening'?t("识别完成后，请确认要制作的类型；现在还不会开始剪辑。"):t("完成后草稿会出现在这里，可以先处理其他项目。")}</div>}
      {workspace.analysis?.status==='failed' && <div className="ac-empty"><b>{t("这次制作未完成")}</b><span className="studio-error">{workspace.analysis.error}</span><Btn onClick={()=>navigate('/settings')}>{t("模型设置")}</Btn></div>}
      {error && <div className="ac-empty"><b>{t("成片草稿加载失败")}</b>{error}<Btn onClick={refresh}>{t("重试")}</Btn></div>}
      <div className="ac-grid-3 studio-result-grid">{workspace.drafts.map(d => <DraftResultCard key={d.id} projectId={project.id} draft={d} jobs={workspace.jobs}
        onEdit={()=>navigate(`/project/${project.id}/studio/${d.id}`)} onExport={()=>setExporting(d)} onHistory={()=>setHistory(true)} />)}{children}</div>
      {!loading&&!error&&!workspace.drafts.length&&!project.clips?.length&&!project.collections?.length&&workspace.analysis?.status!=='running'&&<div className="ac-empty"><b>{t("暂时没有可用成片")}</b>{managed?t("可以重试，或修改制作方案。"):t("可调整最低评分后重试内容处理。")}</div>}
    </Section>}
    {actionError&&<p className="studio-error" role="alert">{actionError}</p>}
    <details className="studio-details studio-source-details"><summary>{visual?t("高光片段"):t("来源片段")} <span className="ac-mono">{workspace.events.length+(project.clips?.length||0)}</span>{t("· 需要换镜头时再选")}</summary>
      {workspace.analysis?.coverage && <p className="studio-muted">{workspace.analysis.coverage.note} {t('全片初筛采样间隔约 {{seconds}} 秒。', { seconds: workspace.analysis.coverage.sample_interval.toFixed(1) })}</p>}
      {workspace.events.map(e=><div className="studio-source-row" key={e.id}><div><b>{e.label}</b><p className="studio-muted">{t('{{start}}–{{end}} 秒', { start: e.start.toFixed(1), end: e.end.toFixed(1) })} · {e.evidence}</p></div><div className="studio-actions"><Btn size="sm" onClick={()=>setPreview(e)}>{t("查看原片")}</Btn><Btn size="sm" disabled={!!busy} loading={busy===e.id} onClick={()=>act(e.id,async()=>{const d=await studioApi.eventDraft(project.id,e.id);navigate(`/project/${project.id}/studio/${d.id}`)})}>{t("用于新成片")}</Btn></div></div>)}
      {project.clips?.map(c=><div className="studio-source-row" key={c.id}><div><b>{c.generated_title||c.title}</b><p className="studio-muted">{c.start_time}–{c.end_time}</p></div><Btn size="sm" disabled={!!busy} loading={busy===c.id} onClick={()=>createLegacy(c)}>{t("用于新成片")}</Btn></div>)}
    </details>
    <details className="studio-details studio-source-details"><summary>{t("原素材")}</summary><video controls preload="none" className="studio-source-video" src={studioApi.source(project.id)}/></details>
    <ExportHistory projectId={project.id} jobs={workspace.jobs} open={history} onClose={()=>setHistory(false)}/>
    <Dialog open={!!preview} title={preview?.label||t("原片")} onClose={()=>setPreview(null)}>{preview&&<video key={preview.id} controls preload="metadata" className="studio-source-video" src={`${studioApi.source(project.id)}#t=${preview.start},${preview.end}`}/>}<p className="studio-muted">{preview?.evidence}</p></Dialog>
    <Dialog open={!!exporting} title={t("导出成片")} onClose={()=>!busy&&setExporting(null)} description={t("按当前草稿设置渲染，完成后在导出记录下载。")} footer={<div className="studio-actions"><Btn disabled={!!busy} onClick={()=>setExporting(null)}>{t("关闭")}</Btn><Btn variant="cta" disabled={!!busy} loading={busy==='export'} onClick={()=>exporting&&act('export',async()=>{await studioApi.export(project.id,exporting.id,exporting.revision);setExporting(null);setHistory(true)})}>{t("确认导出")}</Btn></div>}><p>{exporting?.title}</p><p className="studio-muted">{exporting?.aspect==='portrait'?t("9:16 竖屏"):exporting?.aspect==='landscape'?t("16:9 横屏"):t("原画幅")} · MP4 · 30 fps</p>{actionError&&<p className="studio-error">{actionError}</p>}</Dialog>
  </>
}
