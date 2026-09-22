import { useEffect, useState } from 'react'
import { Btn, Dialog } from '../../ui'
import { Goal, ImportOptions, ImportPlan, defaultImportOptions, goalLabels, languages } from './types'
import ImportPreferences from './ImportPreferences'
import { studioApi, errorText } from './api'

const contentLabels: Record<string,string> = {gameplay:'游戏录屏',talk:'讲解 / 访谈',sport:'运动内容',vlog:'生活记录',mixed:'混合内容',other:'视频内容'}
const choices: {goal:Goal;description:string}[] = [
  {goal:'content',description:'按语音与内容含义，提炼完整片段'},
  {goal:'highlight',description:'找到精彩事件，保留关键过程'},
  {goal:'promo',description:'围绕真实片段，制作不同开头的推广草稿'},
]
export default function PlanSummary({projectId, plan, status, onChanged, onStarted}: {projectId:string;plan?:ImportPlan;status?:string;onChanged:()=>void;onStarted?:()=>void}) {
  const [open,setOpen]=useState(false)
  const [value,setValue]=useState<ImportOptions>({...defaultImportOptions})
  const [selected,setSelected]=useState<Goal[]>([])
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const running=status==='running'
  const awaiting=status==='awaiting_confirmation'
  useEffect(()=>{setSelected(plan?.suggested_goals || []);setValue({...defaultImportOptions,...plan?.overrides});setError('')},[plan?.id])
  const show=()=>{setValue({...defaultImportOptions,...plan?.overrides});setError('');setOpen(true)}
  const apply=async()=>{setBusy(true);setError('');try{await studioApi.correctPlan(projectId,value);setOpen(false);onChanged()}catch(e){setError(errorText(e))}finally{setBusy(false)}}
  const start=async()=>{if(!plan||!selected.length)return;setBusy(true);setError('');try{await studioApi.confirmPlan(projectId,plan.id,selected,value);if(onStarted)onStarted();else onChanged()}catch(e){setError(errorText(e))}finally{setBusy(false)}}
  const prefs=plan?.preferences
  return <>
    <div className={`studio-plan-summary ${awaiting?'studio-plan-confirm':''}`}>
      <div>{prefs?<><b>{awaiting?'这段素材，可以这样做':plan?.mode==='ai'?'AI 建议':plan?.mode==='manual'?'你的方案':'当前方案'}</b><span className="studio-muted">{contentLabels[plan?.content_type || 'other']} · {prefs.goal==='content'?'按完整语义选段':`约 ${prefs.duration} 秒`} · {prefs.aspect==='original'?'保留原画幅':prefs.aspect==='portrait'?'9:16 竖屏':'16:9 横屏'} · {languages.find(l=>l.value===prefs.language)?.label}</span><details><summary>查看判断依据{plan?.mode==='ai' && plan.confidence<.6?' · 识别把握较低':''}</summary><p className="studio-muted">{plan?.reason}</p></details></>:<span className="studio-muted">{running?'快速判断素材适合的制作类型':'可调整制作方案后重新识别'}</span>}</div>
      {awaiting && plan ? <>
        <p className="studio-muted">{plan.suggested_goals.length?'已勾选建议制作的类型，你可以取消或补选。':'本次未能自动推荐，请按素材内容选择制作类型。'}确认后才开始详细理解与剪辑。</p>
        <div className="studio-output-choices">{choices.map(({goal,description})=><label key={goal} className={`studio-output-choice ${selected.includes(goal)?'is-selected':''}`}><input type="checkbox" checked={selected.includes(goal)} disabled={busy} onChange={e=>setSelected(e.target.checked?[...selected,goal]:selected.filter(g=>g!==goal))}/><b>{goalLabels[goal]}</b>{plan.suggested_goals.includes(goal)&&<small>建议</small>}<span className="studio-muted">{description}</span></label>)}</div>
        <details className="studio-details"><summary>调整制作参数（可选）</summary><ImportPreferences value={value} onChange={setValue} hideGoal/></details>
        <div className="studio-row studio-confirm-footer"><span className="studio-muted">{selected.length?`将制作 ${selected.length} 类内容`:'至少选择一种制作类型'}</span><Btn variant="cta" disabled={!selected.length||busy} loading={busy} onClick={start}>确认并开始制作</Btn></div>
      </> : <div className="studio-actions">{plan?.selected_goals&&<span className="studio-muted">{plan.selected_goals.map(g=>goalLabels[g]).join(' / ')}</span>}<Btn size="sm" disabled={running} onClick={show}>修改方案</Btn></div>}
      {!open&&error&&<p className="studio-error" role="alert">{error}</p>}
    </div>
    <Dialog open={open} onClose={()=>!busy&&setOpen(false)} title="调整制作方案" description="使用同一份素材重新推荐，确认后再制作；已有草稿和导出会保留。" footer={<div className="studio-actions"><Btn disabled={busy} onClick={()=>setOpen(false)}>取消</Btn><Btn variant="cta" loading={busy} onClick={apply}>重新推荐</Btn></div>}>
      <ImportPreferences value={value} onChange={setValue}/><label className="studio-field">补充要求<input value={value.instruction} maxLength={1000} onChange={e=>setValue({...value,instruction:e.target.value})}/></label>
      {error&&<p className="studio-error" role="alert">{error}</p>}
    </Dialog>
  </>
}
