import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Btn, Segmented, Dialog } from '../../ui'
import { studioApi, errorText } from './api'
import { defaultImportOptions, goalLabels, ImportOptions } from './types'
import ImportPreferences from './ImportPreferences'
import './studio.css'

export default function CreativeImport({ onImported }: { onImported: () => Promise<void> }) {
  const navigate = useNavigate()
  const [source, setSource] = useState<'link' | 'file'>('link')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [subtitle, setSubtitle] = useState<File | null>(null)
  const [options, setOptions] = useState<ImportOptions>({...defaultImportOptions})
  const [browser, setBrowser] = useState('')
  const [preferences, setPreferences] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const custom = options.goal !== 'auto' || options.language !== 'source' || options.aspect !== null || options.duration !== null || !!subtitle || !!browser
  const submit = async () => {
    if (source === 'file' ? !file : !url.trim()) { setError('请先添加视频文件或链接'); return }
    setBusy(true); setError('')
    try {
      const body = new FormData()
      body.append('goal', options.goal); body.append('language', options.language); body.append('instruction', options.instruction)
      if (options.aspect) body.append('aspect', options.aspect)
      if (options.duration) body.append('duration', String(options.duration))
      if (subtitle) body.append('subtitle', subtitle)
      body.append('name', file && source === 'file' ? file.name.replace(/\.[^.]+$/, '') : '智能剪辑')
      if (source === 'file' && file) body.append('video', file)
      else { body.append('url', url.trim()); if (browser) body.append('browser', browser) }
      const result = await studioApi.import(body)
      // Project refresh should never make a successful import look like an upload failure.
      void onImported().catch(() => undefined)
      navigate(`/import/${result.project_id}`)
    } catch (e) { setError(errorText(e)) } finally { setBusy(false) }
  }
  return <section className="ac-creative-import">
    <h1 className="ac-title">放入视频，AI 帮你剪出精彩。</h1>
    <p className="studio-muted">先识别适合制作的内容，确认后再开始剪辑。</p>
    <div className="studio-import-box">
      <div className="studio-row"><Segmented ariaLabel="导入来源" value={source} onChange={v=>!busy&&setSource(v)} options={[{value:'link',label:'链接导入'},{value:'file',label:'文件导入'}]}/></div>
      {source==='link'?<label className="studio-field"><span className="studio-sr">视频链接</span><textarea placeholder="粘贴 B 站或 YouTube 视频链接" value={url} onChange={e=>setUrl(e.target.value)} disabled={busy}/></label>:<label className="studio-file"><span>{file?.name || '选择一段视频'}</span><input type="file" aria-label="视频文件" accept="video/mp4,video/webm,video/quicktime,.mkv,.avi" disabled={busy} onChange={e=>setFile(e.target.files?.[0] || null)}/><small>MP4 / MOV / MKV / WEBM / AVI</small></label>}
      <details className="studio-details"><summary>有特别要求？（选填）</summary><label className="studio-field"><span className="studio-sr">制作要求</span><input aria-label="制作要求" placeholder="例如：做一条适合竖屏投放的游戏短片" maxLength={1000} value={options.instruction} disabled={busy} onChange={e=>setOptions({...options,instruction:e.target.value})}/></label></details>
      <div className="studio-row studio-import-bottom"><div><span className="studio-muted">{custom?`已调整偏好 · ${goalLabels[options.goal]}`:'AI 推荐制作类型与参数，由你确认'}</span><button className="studio-link studio-preferences-link" disabled={busy} onClick={()=>setPreferences(true)}>调整偏好</button></div><Btn variant="cta" loading={busy} onClick={submit}>{busy?'正在导入':'导入并识别'}</Btn></div>
      {error&&<p className="studio-error" role="alert">{error}</p>}
    </div>
    <Dialog open={preferences} onClose={()=>setPreferences(false)} title="制作偏好" description="默认由 AI 匹配。你指定的选项优先，生成后也可以修改。" footer={<div className="studio-actions"><Btn onClick={()=>{setOptions({...defaultImportOptions,instruction:options.instruction});setSubtitle(null);setBrowser('')}}>恢复自动</Btn><Btn variant="cta" onClick={()=>setPreferences(false)}>完成</Btn></div>}>
      <ImportPreferences value={options} onChange={setOptions}/>
      <label className="studio-field">已有字幕（选填）<input type="file" accept=".srt" aria-label="已有字幕" onChange={e=>setSubtitle(e.target.files?.[0] || null)}/>{subtitle&&<small>{subtitle.name}<button className="studio-link" onClick={()=>setSubtitle(null)}>移除</button></small>}</label>
      {source==='link'&&<details className="studio-details"><summary>下载遇到登录限制时</summary><label className="studio-field">使用浏览器登录状态<select value={browser} onChange={e=>setBrowser(e.target.value)}><option value="">不使用</option>{['chrome','edge','safari','firefox'].map(b=><option key={b}>{b}</option>)}</select></label><p className="studio-muted">仅在下载需要登录时选择，不会自动读取浏览器 Cookie。</p></details>}
    </Dialog>
  </section>
}
