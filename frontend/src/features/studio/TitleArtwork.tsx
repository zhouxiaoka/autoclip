import { useEffect, useState } from 'react'
import { studioApi } from './api'
import { Draft } from './types'

export default function TitleArtwork({projectId, draft}: {projectId:string; draft:Draft}) {
  const [image,setImage]=useState('')
  const [error,setError]=useState('')
  const [retry,setRetry]=useState(0)
  const signature=JSON.stringify([draft.hook,draft.title_style,draft.aspect,draft.title_scale,draft.title_y,draft.title_accent])
  useEffect(()=>{
    const controller=new AbortController()
    let url=''
    setImage('');setError('')
    const timer=setTimeout(()=>{
      studioApi.titlePreview(projectId,draft,controller.signal).then(blob=>{
        if(controller.signal.aborted)return
        url=URL.createObjectURL(blob);setImage(url)
      }).catch(async e=>{
        if(controller.signal.aborted)return
        let message='文字预览暂不可用'
        try { if(e?.response?.data instanceof Blob) message=JSON.parse(await e.response.data.text()).detail || message } catch { /* Keep actionable generic error. */ }
        if(!controller.signal.aborted)setError(message)
      })
    },250)
    return ()=>{clearTimeout(timer);controller.abort();if(url)URL.revokeObjectURL(url)}
  },[projectId,signature,retry])
  return <>{image && <img className="studio-title-art" src={image} alt="标题排版预览"/>}{error && <div className="studio-title-status" role="alert">{error}<button type="button" onClick={()=>setRetry(v=>v+1)}>重试</button></div>}{!image&&!error&&<span className="studio-title-status">生成文字预览…</span>}</>
}
