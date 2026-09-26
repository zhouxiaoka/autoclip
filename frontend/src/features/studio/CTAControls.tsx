import { useEffect, useState } from 'react'
import { t } from '../../i18n'
import { studioApi, errorText } from './api'
import { CTA, CTAPlan, Draft, languages } from './types'

const defaults: CTA = {template:'off',version:1,brand:'',text:'',language:'zh',position:.65,confirmed_scene:''}
const labels = {off:'关闭',auto:'自动推荐',continue:'玩法续播',challenge:'挑战交接',brand:'品牌落版'}
export default function CTAControls({projectId,draft,onChange}: {projectId:string;draft:Draft;onChange:(cta:CTA)=>void}) {
  const c = draft.cta ?? {...defaults,language:draft.language==='en'?'en':draft.language==='ja'?'ja':'zh'}
  const [plan,setPlan]=useState<CTAPlan|null>(null)
  const [error,setError]=useState('')
  const signature=JSON.stringify([c,draft.scenes,draft.aspect])
  useEffect(()=>{
    setPlan(null);setError('')
    if(c.template==='off')return
    const controller=new AbortController()
    const timer=setTimeout(()=>studioApi.ctaPreview(projectId,draft,controller.signal).then(value=>{
      if(!controller.signal.aborted)setPlan(value)
    }).catch(e=>{if(!controller.signal.aborted)setError(errorText(e))}),250)
    return ()=>{controller.abort();clearTimeout(timer)}
  },[projectId,signature])
  const change=(value:Partial<CTA>)=>onChange({...c,...value})
  return <details className="studio-details"><summary>{t('行动引导 CTA')} · {t(labels[c.template])}</summary>
    <label className="studio-field">{t('收尾方式')}<select value={c.template} onChange={e=>change({template:e.target.value as CTA['template']})}>{Object.entries(labels).map(([value,label])=><option key={value} value={value}>{t(label)}</option>)}</select></label>
    {c.template!=='off' && <>
      <p className="studio-muted">{t('按镜头时长推荐；不调用模型。请核对玩法结果与遮挡。')}</p>
      <label className="studio-field">{t('游戏名称（可选）')}<input maxLength={40} value={c.brand} onChange={e=>change({brand:e.target.value})}/></label>
      <label className="studio-field">{t('默认行动文案语言')}<select value={c.language} onChange={e=>change({language:e.target.value as CTA['language']})}>{languages.filter(l=>l.value!=='source').map(l=><option key={l.value} value={l.value}>{l.label}</option>)}</select></label>
      <label className="studio-field">{t('行动文案（留空使用默认）')}<textarea maxLength={80} value={c.text} onChange={e=>change({text:e.target.value})}/></label>
      <p className="studio-muted">{t('自定义文案与游戏名称按原文输出，不自动翻译。')}</p>
      {c.template==='challenge' && <label><input type="checkbox" checked={!!plan && c.confirmed_scene===plan.scene_key} onChange={e=>change({confirmed_scene:e.target.checked && plan?plan.scene_key:''})} disabled={!plan}/>{t('我已确认末镜头包含完整结果，适合定格')}</label>}
      {plan?.template!=='brand' && <label className="studio-field">{t('文字位置')}<input type="range" min=".2" max=".7" step=".01" value={c.position} onChange={e=>change({position:Number(e.target.value)})}/></label>}
      {error && <p className="studio-error" role="alert">{t(error)}</p>}
      {plan && <><p>{t(labels[plan.template])} · {t(plan.reason)} · +{plan.extra_duration}s</p><img src={plan.image} style={{width:'100%',maxHeight:320,objectFit:'contain',background:'#263544'}} alt={t('CTA 排版预览')}/></>}
      <p className="studio-muted">{t('此处仅预览文字图层；完整画面、定格与声音请导出后预览。')}</p>
      <p className="studio-muted">{t('CTA 为视频内文字，实际点击入口需在投放平台配置')}</p>
    </>}
  </details>
}
