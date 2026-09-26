import { useTranslation } from 'react-i18next'
import { t } from '../../i18n'
import { useEffect, useState } from 'react'
import { Btn, Dialog, fmtDuration } from '../../ui'
import { AnalysisMode, Goal, ImportOptions, ImportPlan, defaultImportOptions, goalLabels, languages } from './types'
import ImportPreferences from './ImportPreferences'
import { studioApi, errorText } from './api'

const contentLabels: Record<string,string> = {gameplay:'游戏录屏',talk:'讲解 / 访谈',sport:'运动内容',vlog:'生活记录',mixed:'混合内容',other:'视频内容'}
const choices: {goal:Goal;description:string}[] = [
  {goal:'content',description:'按语音与内容含义，提炼完整片段'},
  {goal:'highlight',description:'找到精彩事件，保留关键过程'},
  {goal:'promo',description:'围绕真实片段，制作不同开头的推广草稿'},
]
export default function PlanSummary({projectId, plan, status, onChanged, onStarted}: {projectId:string;plan?:ImportPlan;status?:string;onChanged:()=>void;onStarted?:()=>void}) {
  useTranslation()
  const [analysisMode,setAnalysisMode]=useState<AnalysisMode>('subtitle')
  const [capability,setCapability]=useState<{visual_analysis:boolean;visual_model:string}|null>(null)
  useEffect(()=>{let live=true;studioApi.capabilities().then(v=>{if(live)setCapability(v)}).catch(()=>{if(live)setCapability(null)});return()=>{live=false}},[])
  const [open,setOpen]=useState(false)
  const [value,setValue]=useState<ImportOptions>({...defaultImportOptions})
  const [selected,setSelected]=useState<Goal[]>([])
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const running=status==='running'
  const awaiting=status==='awaiting_confirmation'
  useEffect(()=>{setAnalysisMode(plan?.recommended_analysis || 'subtitle');setSelected(plan?.suggested_goals || []);setValue({...defaultImportOptions,...plan?.overrides});setError('')},[plan?.id])
  const show=()=>{setValue({...defaultImportOptions,...plan?.overrides});setError('');setOpen(true)}
  const apply=async()=>{setBusy(true);setError('');try{await studioApi.correctPlan(projectId,value);setOpen(false);onChanged()}catch(e){setError(t(errorText(e)))}finally{setBusy(false)}}
  const start=async()=>{if(!plan||!selected.length)return;setBusy(true);setError('');try{await studioApi.confirmPlan(projectId,plan.id,selected,value,analysisMode);if(onStarted)onStarted();else onChanged()}catch(e){setError(t(errorText(e)))}finally{setBusy(false)}}
  const incompatible=analysisMode==='subtitle'?selected.some(g=>g!=='content'):selected.length===1&&selected[0]==='content'
  const unavailable=analysisMode==='visual'&&!capability?.visual_analysis
  const prefs=plan?.preferences
  return <>
    <div className={`studio-plan-summary ${awaiting?'studio-plan-confirm':''}`}>
      <div>{prefs?<><b>{awaiting?t("这段素材，可以这样做"):plan?.mode==='ai'?t("AI 建议"):plan?.mode==='manual'?t("你的方案"):t("当前方案")}</b><span className="studio-muted">{t(contentLabels[plan?.content_type || 'other'] ?? contentLabels.other)}{plan?.source_duration!=null?` · ${t('原素材 {{duration}}', { duration: fmtDuration(plan.source_duration) })}`:''} · {prefs.goal==='content'?t("按完整语义选段"):t('每条参考 {{seconds}} 秒', { seconds: prefs.duration })} · {prefs.aspect==='original'?t("保留原画幅"):prefs.aspect==='portrait'?t("9:16 竖屏"):t("16:9 横屏")} · {prefs.language==='source' ? t('原语言') : languages.find(l=>l.value===prefs.language)?.label}</span><details><summary>{t("查看判断依据")}{plan?.mode==='ai' && plan.confidence<.6?t("· 识别把握较低"):''}</summary><p className="studio-muted">{t(plan?.reason || '')}</p></details></>:<span className="studio-muted">{running?t("快速判断素材适合的制作类型"):t("可调整制作方案后重新识别")}</span>}</div>
      {awaiting && plan ? <>
        <label className="studio-field">{t("本次分析方式")}<select disabled={busy} value={analysisMode} onChange={e=>setAnalysisMode(e.target.value as AnalysisMode)}><option value="subtitle">{t("字幕分析 · 低成本")}</option><option value="visual">{t("视觉分析")}</option></select></label>
        <p className="studio-muted">{t(analysisMode==='subtitle'?"仅分析字幕文本；无字幕时需要转写。":"发送抽样画面与文本，按模型服务商计费。")}{analysisMode==='visual'&&capability?.visual_model?` · ${capability.visual_model}`:''}</p>
        {unavailable&&<p role="alert" className="studio-error">{t("视觉模型不可用，请前往模型设置。")}</p>}
        {incompatible&&<p role="alert" className="studio-error">{t("当前内容切片使用字幕分析；高光和推广使用视觉分析。请调整方式或制作类型。")}</p>}
        <p className="studio-muted">{plan.suggested_goals.length?t("已勾选建议制作的类型，你可以取消或补选。"):t("本次未能自动推荐，请按素材内容选择制作类型。")}{' '}{t("确认后才开始详细理解与剪辑。")}</p>
        <div className="studio-output-choices">{choices.map(({goal,description})=><label key={goal} className={`studio-output-choice ${selected.includes(goal)?'is-selected':''}`}><input type="checkbox" checked={selected.includes(goal)} disabled={busy} onChange={e=>setSelected(e.target.checked?[...selected,goal]:selected.filter(g=>g!==goal))}/><b>{t(goalLabels[goal])}</b>{plan.suggested_goals.includes(goal)&&<small>{t("建议")}</small>}<span className="studio-muted">{t(description)}</span></label>)}</div>
        <details className="studio-details"><summary>{t("调整制作参数（可选）")}</summary><ImportPreferences value={value} onChange={setValue} hideGoal/></details>
        <div className="studio-row studio-confirm-footer"><span className="studio-muted">{selected.length?t('将制作 {{count}} 类内容', { count: selected.length }):t("至少选择一种制作类型")}</span><Btn variant="cta" disabled={!selected.length||busy||incompatible||unavailable} loading={busy} onClick={start}>{t("确认并开始制作")}</Btn></div>
      </> : <div className="studio-actions">{plan?.selected_goals&&<span className="studio-muted">{plan.selected_goals.map(g=>t(goalLabels[g])).join(' / ')}</span>}<Btn size="sm" disabled={running} onClick={show}>{t("修改方案")}</Btn></div>}
      {!open&&error&&<p className="studio-error" role="alert">{error}</p>}
    </div>
    <Dialog open={open} onClose={()=>!busy&&setOpen(false)} title={t("调整制作方案")} description={t("使用同一份素材重新推荐，确认后再制作；已有草稿和导出会保留。")} footer={<div className="studio-actions"><Btn disabled={busy} onClick={()=>setOpen(false)}>{t("取消")}</Btn><Btn variant="cta" loading={busy} onClick={apply}>{t("重新推荐")}</Btn></div>}>
      <ImportPreferences value={value} onChange={setValue}/><label className="studio-field">{t("补充要求")}<input value={value.instruction} maxLength={1000} onChange={e=>setValue({...value,instruction:e.target.value})}/></label>
      {error&&<p className="studio-error" role="alert">{error}</p>}
    </Dialog>
  </>
}
