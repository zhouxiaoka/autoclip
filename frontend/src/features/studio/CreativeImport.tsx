import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import FileUpload from '../../components/FileUpload'
import BilibiliDownload from '../../components/BilibiliDownload'
import { Btn, Segmented } from '../../ui'
import { studioApi, errorText } from './api'
import { Goal, languages, Language } from './types'
import './studio.css'

export default function CreativeImport({ onImported }: { onImported: () => Promise<void> }) {
  const navigate = useNavigate()
  const [source, setSource] = useState<'link' | 'file'>('link')
  const [goal, setGoal] = useState<Goal>('content')
  const [visual, setVisual] = useState<boolean | null>(null)
  const [url, setUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [language, setLanguage] = useState<Language>('source')
  const [aspect, setAspect] = useState('portrait')
  const [duration, setDuration] = useState('30')
  const [browser, setBrowser] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { let live = true; studioApi.capabilities().then(c => live && setVisual(c.visual_analysis)).catch(() => live && setVisual(false)); return () => { live = false } }, [])
  const submit = async () => {
    if (source === 'file' ? !file : !url.trim()) { setError('请先添加视频文件或链接'); return }
    setBusy(true); setError('')
    try {
      const body = new FormData()
      body.append('goal', goal); body.append('language', language); body.append('aspect', aspect); body.append('duration', duration)
      body.append('name', file && source === 'file' ? file.name.replace(/\.[^.]+$/, '') : '游戏成片')
      if (source === 'file' && file) body.append('video', file)
      else { body.append('url', url.trim()); if (browser) body.append('browser', browser) }
      const result = await studioApi.import(body)
      await onImported()
      navigate(`/project/${result.project_id}`)
    } catch (e) { setError(errorText(e)) } finally { setBusy(false) }
  }
  return <section className="ac-creative-import">
    <h1 className="ac-title">导入视频，AI 帮你剪出精彩内容。</h1>
    <p className="studio-muted">访谈、分享、游戏录屏，都从这里开始。</p>
    <div className="studio-import-box">
      <div className="studio-row"><Segmented ariaLabel="导入来源" value={source} onChange={v => !busy && setSource(v)} options={[{ value: 'link', label: '链接导入' }, { value: 'file', label: '文件导入' }]} /></div>
      <div className="studio-row studio-goal"><span>我想做</span><Segmented ariaLabel="创作目标" value={goal} onChange={v => !busy && setGoal(v)} options={[{ value: 'content', label: '内容切片' }, { value: 'highlight', label: '精彩高光' }, { value: 'promo', label: '推广成片' }]} /></div>
      {goal === 'content' ? <div className="studio-legacy-import">{source === 'link' ? <BilibiliDownload onDownloadSuccess={() => { void onImported() }} /> : <FileUpload onUploadSuccess={() => { void onImported() }} />}</div> : <>
        {source === 'link' ? <label className="studio-field"><span className="studio-sr">视频链接</span><textarea placeholder="粘贴 B 站或 YouTube 视频链接" value={url} onChange={e => setUrl(e.target.value)} disabled={busy} /></label> : <label className="studio-file"><span>{file?.name || '选择一段游戏录屏'}</span><input type="file" accept="video/mp4,video/webm,video/quicktime,.mkv,.avi" disabled={busy} onChange={e => setFile(e.target.files?.[0] || null)} /><small>MP4 / MOV / MKV / WEBM / AVI</small></label>}
        <details className="studio-details"><summary>更多设置 · 时长、语言与画幅</summary><div className="studio-fields">
          <label className="studio-field">期望时长<select value={duration} onChange={e => setDuration(e.target.value)} disabled={busy}><option value="15">约 15 秒</option><option value="30">约 30 秒</option><option value="60">约 60 秒</option></select></label>
          <label className="studio-field">文字语言<select value={language} onChange={e => setLanguage(e.target.value as Language)} disabled={busy}>{languages.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}</select></label>
          <label className="studio-field">画幅<select value={aspect} onChange={e => setAspect(e.target.value)} disabled={busy}><option value="portrait">9:16 竖屏</option><option value="landscape">16:9 横屏</option><option value="original">保持原画幅</option></select></label>
          {source === 'link' && <label className="studio-field">浏览器 Cookie<select value={browser} onChange={e => setBrowser(e.target.value)} disabled={busy}><option value="">不使用</option>{['chrome', 'edge', 'safari', 'firefox'].map(b => <option key={b}>{b}</option>)}</select></label>}
        </div></details>
        {visual === false && <p className="studio-muted">视觉模型尚未配置。<button className="studio-link" onClick={() => navigate('/settings?section=vision')}>前往设置视觉模型 →</button></p>}
        <div className="studio-row studio-import-bottom"><span className="studio-muted">{goal === 'highlight' ? '发现关键事件，保留精彩过程' : '同一段真实玩法，生成不同开头'}</span><Btn variant="cta" loading={busy} disabled={visual !== true} onClick={submit}>{busy ? '正在导入' : '开始生成'}</Btn></div>
      </>}
      {error && <p className="studio-error" role="alert">{error}</p>}
    </div>
  </section>
}
