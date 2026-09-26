import { useTranslation } from 'react-i18next'
import { t } from '../../i18n'
import { useEffect, useState } from 'react'
import { studioApi } from './api'
import { Draft } from './types'

export default function TitleArtwork({projectId, draft}: {projectId:string; draft:Draft}) {
  useTranslation()
  const [image,setImage]=useState('')
  const [mask,setMask]=useState('')
  const [error,setError]=useState('')
  const [retry,setRetry]=useState(0)
  const signature=JSON.stringify([draft.hook,draft.title_style,draft.title_template_version,draft.aspect,draft.title_scale,draft.title_y,draft.title_accent])
  useEffect(()=>{
    const controller=new AbortController()
    const urls:string[]=[]
    setImage('');setMask('');setError('')
    const timer=setTimeout(()=>{
      Promise.all([studioApi.titlePreview(projectId,draft,controller.signal), draft.title_style==='frosted'?studioApi.titlePreview(projectId,draft,controller.signal,'backdrop'):Promise.resolve(null)]).then(([blob,backdrop])=>{
        if(controller.signal.aborted)return
        const url=URL.createObjectURL(blob);urls.push(url);setImage(url)
        if(backdrop){const maskUrl=URL.createObjectURL(backdrop);urls.push(maskUrl);setMask(maskUrl)}
      }).catch(async e=>{
        if(controller.signal.aborted)return
        let message=t("文字预览暂不可用")
        try { if(e?.response?.data instanceof Blob) message=JSON.parse(await e.response.data.text()).detail || message } catch { /* Keep actionable generic error. */ }
        if(!controller.signal.aborted)setError(message)
      })
    },250)
    return ()=>{clearTimeout(timer);controller.abort();urls.forEach(url=>URL.revokeObjectURL(url))}
  },[projectId,signature,retry])
  return <>{mask && <div className="studio-title-backdrop" style={{maskImage:`url(${mask})`,WebkitMaskImage:`url(${mask})`}}/>}{image && <img className="studio-title-art" src={image} alt={t("标题排版预览")}/>}{error && <div className="studio-title-status" role="alert">{error}<button type="button" onClick={()=>setRetry(v=>v+1)}>{t("重试")}</button></div>}{!image&&!error&&<span className="studio-title-status">{t("生成文字预览…")}</span>}</>
}
