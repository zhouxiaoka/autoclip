import { useEffect, useState, useRef } from 'react'
import { t } from '../../i18n'
import { studioApi, errorText } from './api'
import { CTA, CTAPlan, Draft, languages } from './types'

const defaults: CTA = {template:'off',version:1,brand:'',text:'',language:'zh',position:.65,confirmed_scene:''}
const styles = {glossy:'玩具厚边',soft:'轻量休闲',tactical:'硬朗任务框',type:'大字邀请'}
const accents = {glossy:'#8ac514',soft:'#68cf43',tactical:'#f1df50',type:'#ffffff'}
const labels = {off:'关闭',auto:'自动推荐',continue:'玩法续播',challenge:'挑战交接',brand:'品牌落版'}
export default function CTAControls({projectId,draft,onChange}: {projectId:string;draft:Draft;onChange:(cta:CTA)=>void}) {
  const c = draft.cta ?? {...defaults,language:draft.language==='en'?'en':draft.language==='ja'?'ja':'zh'}
  const currentCTA=useRef(c)
  currentCTA.current=c
  const [plan,setPlan]=useState<CTAPlan|null>(null)
  const [error,setError]=useState('')
  const [assetError,setAssetError]=useState('')
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
  const readAsset=async (key:'logo'|'icon'|'brand_art',file?:File)=>{
    if(!file)return
    setAssetError('')
    if(file.size>512*1024 || !['image/png','image/jpeg','image/webp'].includes(file.type)){
      setAssetError('品牌图片需为 PNG、JPEG 或 WebP，且不超过 512 KB');return
    }
    try {
      const value=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=reject;reader.readAsDataURL(file)})
      onChange({...currentCTA.current,[key]:value})
    }catch{setAssetError('读取品牌图片失败')}
  }
  return <details className="studio-details"><summary>{t('行动引导 CTA')} · {t(labels[c.template])}</summary>
    <label className="studio-field">{t('收尾方式')}<select value={c.template} onChange={e=>change({template:e.target.value as CTA['template']})}>{Object.entries(labels).map(([value,label])=><option key={value} value={value}>{t(label)}</option>)}</select></label>
    {c.template!=='off' && <>
      <p className="studio-muted">{t('按镜头时长推荐；不调用模型。请核对玩法结果与遮挡。')}</p>
      <label className="studio-field">{t('CTA 视觉风格')}<select value={c.style??'glossy'} onChange={e=>change({style:e.target.value as CTA['style']})}>{Object.entries(styles).map(([value,label])=><option key={value} value={value}>{t(label)}</option>)}</select></label>
      <label className="studio-field">{t('CTA 强调色')}<input type="color" value={c.accent??accents[c.style??'glossy']} onChange={e=>change({accent:e.target.value})}/></label>
      {c.accent && <button type="button" onClick={()=>change({accent:null})}>{t('恢复风格默认色')}</button>}
      <p className="studio-muted">{t('按素材画风选择；当前不会自动识别风格。')}</p>
      <label className="studio-field">{t('游戏名称（可选）')}<input maxLength={40} value={c.brand} onChange={e=>change({brand:e.target.value})}/></label>
      <details><summary>{t('品牌素材与完整尾卡')}</summary>
        <label className="studio-field">{t('完整品牌尾卡')}<input type="checkbox" checked={c.brand_layout==='poster'} onChange={e=>change({brand_layout:e.target.checked?'poster':'classic'})}/></label>
        <p className="studio-muted">{t('用于品牌落版：Logo 优先；未提供时使用游戏名称设计字。')}</p>
        <p className="studio-muted">{t('主视觉优先完整展示，不再叠加游戏名称、Logo 或 icon。')} </p>
        <label className="studio-field">{t('品牌标语')}<input maxLength={60} value={c.slogan??''} onChange={e=>change({slogan:e.target.value})}/></label>
        {(['logo','icon','brand_art'] as const).map(key=><div key={key}>
          <label className="studio-field">{key==='logo'?'Logo':key==='icon'?'App icon':t('品牌主视觉（含 Logo）')}<input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>{void readAsset(key,e.target.files?.[0]);e.target.value=''}}/></label>
          {c[key] && <><img src={c[key]??''} alt={key} style={{maxWidth:120,maxHeight:80,objectFit:'contain'}}/><button type="button" onClick={()=>change({[key]:null})}>{t('移除品牌图片')}</button></>}
        </div>)}
        <p className="studio-muted">{t('品牌图片随草稿保存；复制版本时可复用。仅使用你确认的品牌素材。')}</p>
        {assetError && <p role="alert">{t(assetError)}</p>}
      </details>
      <label className="studio-field">{t('默认行动文案语言')}<select value={c.language} onChange={e=>change({language:e.target.value as CTA['language']})}>{languages.filter(l=>l.value!=='source').map(l=><option key={l.value} value={l.value}>{l.label}</option>)}</select></label>
      <label className="studio-field">{t('行动文案（留空使用默认）')}<textarea maxLength={80} value={c.text} onChange={e=>change({text:e.target.value})}/></label>
      <p className="studio-muted">{t('自定义文案与游戏名称按原文输出，不自动翻译。')}</p>
      {c.template==='challenge' && <label><input type="checkbox" checked={!!plan && c.confirmed_scene===plan.scene_key} onChange={e=>change({confirmed_scene:e.target.checked && plan?plan.scene_key:''})} disabled={!plan}/>{t('我已确认末镜头包含完整结果，适合定格')}</label>}
      {plan?.template!=='brand' && <label className="studio-field">{t('文字位置')}<input type="range" min=".2" max=".7" step=".01" value={c.position} onChange={e=>change({position:Number(e.target.value)})}/></label>}
      {error && <p className="studio-error" role="alert">{t(error)}</p>}
      {plan && <><p>{t(labels[plan.template])} · {t(plan.reason)} · +{plan.extra_duration}s</p><img src={plan.image} style={{width:'100%',maxHeight:320,objectFit:'contain',background:'#263544'}} alt={t('CTA 排版预览')}/></>}
      <p className="studio-muted">{t('此处预览收尾排版；完整画面、定格与声音请导出后预览。')}</p>
      <p className="studio-muted">{t('CTA 为视频内文字，实际点击入口需在投放平台配置')}</p>
    </>}
  </details>
}
