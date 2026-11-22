import { useTranslation } from 'react-i18next'
import { t } from '../../i18n'
import { useEffect, useState } from 'react'
import { Btn, Row, Segmented, fmtDuration } from '../../ui'
import { AnalysisMode, Goal, ImportOptions, ImportPlan, defaultImportOptions, goalLabels, languages } from './types'
import PlanEditDialog from './PlanEditDialog'
import ImportPreferences from './ImportPreferences'
import { studioApi, errorText, errorCode } from './api'
import { useNavigate } from 'react-router-dom'
import { speechApi } from '../../services/api'
import TranscriptionGatePrompt from './TranscriptionGatePrompt'
import { isRecoveryCode, probeConfig } from './transcriptionRecovery'
import { useTranscriptionRecovery } from './useTranscriptionRecovery'

const contentLabels: Record<string,string> = {gameplay:'游戏录屏',talk:'讲解 / 访谈',sport:'运动内容',vlog:'生活记录',mixed:'混合内容',other:'视频内容'}
const choices: {goal:Goal;description:string}[] = [
  {goal:'content',description:'按语音与内容含义，提炼完整片段'},
  {goal:'highlight',description:'找到精彩事件，保留关键过程'},
  {goal:'promo',description:'围绕真实片段，制作不同开头的推广草稿'},
]
export default function PlanSummary({projectId, plan, status, onChanged, onStarted, remake}: {projectId:string;plan?:ImportPlan;status?:string;onChanged:()=>void;onStarted?:()=>void;remake?:boolean}) {
  useTranslation()
  const [analysisMode,setAnalysisMode]=useState<AnalysisMode>('subtitle')
  const [capability,setCapability]=useState<{visual_analysis:boolean;visual_model:string}|null>(null)
  useEffect(()=>{let live=true;studioApi.capabilities().then(v=>{if(live)setCapability(v)}).catch(()=>{if(live)setCapability(null)});return()=>{live=false}},[])
  const [open,setOpen]=useState(false)
  const [value,setValue]=useState<ImportOptions>({...defaultImportOptions})
  const [selected,setSelected]=useState<Goal[]>([])
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  // #418 rewrite: a coded gate 422 on confirm opens the same recovery controller as the import page (by code, never text).
  const [recovery,recover]=useTranscriptionRecovery({readiness:signal=>studioApi.readinessProbe(signal),getRuntimeStatus:signal=>speechApi.getRuntimeStatus(probeConfig(signal)),getModels:signal=>speechApi.getModels(probeConfig(signal)),installRuntime:signal=>speechApi.installRuntime({signal}),downloadModel:(model,signal)=>speechApi.downloadModel(model,{signal})},{onReady:()=>{recover.close();void start()}})
  const navigate=useNavigate()
  const running=status==='running'
  const awaiting=status==='awaiting_confirmation'
  useEffect(()=>{setAnalysisMode(plan?.recommended_analysis || 'subtitle');setSelected(plan?.suggested_goals || []);setValue({...defaultImportOptions,...plan?.overrides});setError('')},[plan?.id])
  const show=()=>{setError('');setOpen(true)}
  const start=async()=>{if(!plan||!selected.length)return;setBusy(true);setError('');recover.close();try{await studioApi.confirmPlan(projectId,plan.id,selected,value,analysisMode);if(onStarted)onStarted();else onChanged()}catch(e){const code=errorCode(e);if(isRecoveryCode(code))recover.open(code as string);else setError(t(errorText(e)))}finally{setBusy(false)}}
  const incompatible=analysisMode==='visual'&&selected.length===1&&selected[0]==='content'
  const unavailable=analysisMode==='visual'&&!capability?.visual_analysis
  const prefs=plan?.preferences
  const aspectLabel=(aspect:string)=>t(aspect==='portrait'?'9:16 竖屏':aspect==='landscape'?'16:9 横屏':'保留原画幅')
  const aspectSummary=awaiting&&selected.length?selected.map(goal=>`${t(goalLabels[goal])} · ${aspectLabel(value.aspect || (goal==='promo'?'portrait':plan?.aspect || 'original'))}`).join(' / '):aspectLabel(prefs?.aspect || 'original')
  const controls = awaiting && plan && <>
    <Row label={t("分析方式")} hint={analysisMode==='visual'
        ? <>{t("会抽样几张画面一起分析，更懂动作与场景；按模型服务商计费。")}{capability?.visual_model?` · ${capability.visual_model}`:''}</>
        : unavailable ? t("当前模型不支持画面分析；换一个多模态模型后可开启。") : t("只分析字幕文本，成本最低；没有字幕时会先转写。")}>
      <Segmented size="sm" ariaLabel={t("分析方式")} value={analysisMode} onChange={value=>!busy&&setAnalysisMode(value)}
        options={[{value:'subtitle',label:t("仅字幕")},{value:'visual',label:t("字幕 + 画面")}]} />
    </Row>
    <p className="studio-muted">{plan.suggested_goals.length?t("已勾选建议制作的类型，你可以取消或补选。"):t("本次未能自动推荐，请按素材内容选择制作类型。")}{' '}{t("确认后才开始详细理解与剪辑。")}</p>
    <div className="studio-output-choices">{choices.map(({goal,description})=><label key={goal} className={`studio-output-choice ${selected.includes(goal)?'is-selected':''}`}><input type="checkbox" checked={selected.includes(goal)} disabled={busy} onChange={e=>setSelected(e.target.checked?[...selected,goal]:selected.filter(g=>g!==goal))}/><b>{t(goalLabels[goal])}</b>{plan.suggested_goals.includes(goal)&&<small>{t("建议")}</small>}<span className="studio-muted">{t(goal==='highlight'&&analysisMode==='subtitle'?'按字幕找到高潮句，保留前后关键过程':description)}</span></label>)}</div>
    {remake ? <ImportPreferences value={value} onChange={setValue} hideGoal/> :
      <details className="studio-details"><summary>{t("调整制作参数（可选）")}</summary><ImportPreferences value={value} onChange={setValue} hideGoal/></details>}
  </>
  return <>
    <div className={`studio-plan-summary ${remake ? 'studio-remake-review' : ''} ${awaiting?'studio-plan-confirm':''}`}>
      {plan?.degrade_reason==='vision_unavailable_subtitle_fallback'&&<p role="status" className="studio-muted">{t('视觉服务暂不可用，已切换为字幕分析继续制作。')}</p>}
      {plan?.degrade_reason==='vision_invalid_subtitle_fallback'&&<p role="status" className="studio-muted">{t('画面结果不可用，已改用字幕继续制作。')}</p>}
      {plan?.degrade_reason==='frame_extract_subtitle_fallback'&&<p role="status" className="studio-muted">{t('读取素材画面失败，已改用字幕分析继续制作。')}</p>}
      {plan?.degrade_reason==='source_too_long_subtitle_route'&&<p role="status" className="studio-muted">{t('画面分析最长支持 120 分钟的素材，已改用字幕分析继续制作。')}</p>}
      {remake && prefs ? <div className="studio-remake-heading">
        <h2 className="ac-h2">{t('确认新方案')}</h2>
        <p className="studio-muted">{[
          selected.length ? aspectSummary : null,
          selected.some(goal => goal !== 'content') ? t('约 {{seconds}} 秒', {seconds: value.duration ?? prefs.duration}) : null,
          value.language === 'source' ? t('原语言') : languages.find(l => l.value === value.language)?.label,
          t(analysisMode === 'visual' ? '字幕 + 画面' : '仅字幕'),
        ].filter(Boolean).join(' · ')}</p>
        {plan.mode === 'ai' && plan.reason && <p className="studio-muted">{t(plan.reason)}</p>}
      </div> : (
      <div>{prefs?<><b>{awaiting?t("这段素材，可以这样做"):plan?.mode==='ai'?t("AI 建议"):plan?.mode==='manual'?t("你的方案"):t("当前方案")}</b><span className="studio-muted">{t(contentLabels[plan?.content_type || 'other'] ?? contentLabels.other)}{plan?.source_duration!=null?` · ${t('原素材 {{duration}}', { duration: fmtDuration(plan.source_duration) })}`:''} · {prefs.goal==='content'?t("按完整语义选段"):t('每条参考 {{seconds}} 秒', { seconds: prefs.duration })} · {aspectSummary} · {prefs.language==='source' ? t('原语言') : languages.find(l=>l.value===prefs.language)?.label}</span><details><summary>{t("查看判断依据")}{plan?.mode==='ai' && plan.confidence<.6?t("· 识别把握较低"):''}</summary><p className="studio-muted">{t(plan?.reason || '')}</p></details></>:<span className="studio-muted">{running?t("快速判断素材适合的制作类型"):t("可调整制作方案后重新识别")}</span>}</div>
      )}
      {awaiting && plan ? <>
        {remake ? <details className="studio-remake-controls" open={!plan.suggested_goals.length || undefined}>
          <summary>{t("修改方案")}</summary>
          {controls}
        </details> : controls}
        {unavailable&&<p role="alert" className="studio-error">{t("当前模型不支持画面分析，请先选「仅字幕」，或到设置换一个多模态模型。")}</p>}
        {incompatible&&<p role="alert" className="studio-error">{t("「内容切片」只按字幕分析；要用画面分析，请同时勾选高光或推广。")}</p>}
        {analysisMode==='subtitle'&&selected.includes('promo')&&<p className="studio-muted">{t("字幕推广会额外调用一次文字模型生成文案，按服务商计费；请复核后使用。")}</p>}
        {remake && analysisMode === 'visual' && <p className="studio-muted">{t("会抽样几张画面一起分析，更懂动作与场景；按模型服务商计费。")}</p>}
        <div className="studio-row studio-confirm-footer"><span className="studio-muted">{selected.length?t('将制作 {{count}} 类内容', { count: selected.length }):t("至少选择一种制作类型")}</span><Btn variant="cta" disabled={!selected.length||busy||incompatible||unavailable} loading={busy} onClick={start}>{t("确认并开始制作")}</Btn></div>
      </> : <div className="studio-actions">{plan?.selected_goals&&<span className="studio-muted">{plan.selected_goals.map(g=>t(goalLabels[g])).join(' / ')}</span>}<Btn size="sm" disabled={running} onClick={show}>{t("修改方案")}</Btn></div>}
      {!open&&<TranscriptionGatePrompt state={recovery} busy={busy} onInstall={()=>recover.install()} onRetry={()=>recover.retry()} onContinue={()=>{recover.close();void start()}} navigate={navigate}/>}
      {!open&&error&&<p className="studio-error" role="alert">{error}</p>}
    </div>
    {open && <PlanEditDialog projectId={projectId} plan={plan} onClose={() => setOpen(false)}
      onSubmitted={() => { setOpen(false); onChanged() }} />}
  </>
}
