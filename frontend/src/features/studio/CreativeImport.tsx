import { trackExperience } from '../../analytics/experience'
import { useTranslation } from 'react-i18next'
import { t } from '../../i18n'
import { useState } from 'react'
import { Select } from 'antd'
import { useNavigate } from 'react-router-dom'
import { Btn, Segmented, Dialog } from '../../ui'
import PlatformPicker from './PlatformPicker'
import { studioApi, errorText } from './api'
import { trackQuickOutputPlatforms } from '../../analytics/studio'
import { defaultImportOptions, ImportOptions } from './types'
import ImportPreferences from './ImportPreferences'
import './studio.css'
import './quick-output.css'

export default function CreativeImport({ onImported, blocked = false, onBlocked }: { onImported: () => Promise<void>; blocked?: boolean; onBlocked?: () => void }) {
  useTranslation()
  const navigate = useNavigate()
  const [source, setSource] = useState<'link' | 'file'>('link')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [subtitle, setSubtitle] = useState<File | null>(null)
  const [options, setOptions] = useState<ImportOptions>({...defaultImportOptions})
  const [browser, setBrowser] = useState('')
  const [platforms, setPlatforms] = useState<string[]>(['douyin'])
  const [preferences, setPreferences] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submit = async () => {
    if (blocked) { trackExperience('import_blocked', { reason: 'setup_required', placement: 'home_setup' }); setError(t("请先连接 AI 服务，再导入视频。")); onBlocked?.(); return }
    if (source === 'file' ? !file : !url.trim()) { setError(t("请先添加视频文件或链接")); return }
    setBusy(true); setError('')
    try {
      const body = new FormData()
      body.append('goal', options.goal); body.append('language', options.language); body.append('instruction', options.instruction)
      platforms.forEach(platform => body.append('platforms', platform))
      body.append('auto_start', 'true')
      body.append('portrait_style', options.portrait_style || 'auto')
      if (options.aspect) body.append('aspect', options.aspect)
      if (options.duration) body.append('duration', String(options.duration))
      if (subtitle) body.append('subtitle', subtitle)
      body.append('name', file && source === 'file' ? file.name.replace(/\.[^.]+$/, '') : t("智能剪辑"))
      if (source === 'file' && file) body.append('video', file)
      else { body.append('url', url.trim()); if (browser) body.append('browser', browser) }
      const result = await studioApi.import(body)
      trackQuickOutputPlatforms({ platform_count: platforms.length, portrait_style: options.portrait_style || 'auto' })
      // Project refresh should never make a successful import look like an upload failure.
      void onImported().catch(() => undefined)
      navigate(`/project/${result.project_id}`)
    } catch (e) { setError(t(errorText(e))) } finally { setBusy(false) }
  }
  return <section className="ac-creative-import">
    <h1 className="ac-title">{t("放入视频，直接生成可发布成片。")}</h1>
    <p className="studio-muted">{t("选择发布平台，AI 会自动挑选内容、完成剪辑与渲染。生成后可直接下载或继续编辑。")}</p>
    <div className="studio-import-box">
      <div className="studio-row"><Segmented ariaLabel={t("导入来源")} value={source} onChange={v=>!busy&&setSource(v)} options={[{value:'link',label:t("链接导入")},{value:'file',label:t("文件导入")}]}/></div>
      {source==='link'?<label className="studio-field"><span className="studio-sr">{t("视频链接")}</span><textarea placeholder={t("粘贴 B 站或 YouTube 视频链接")} value={url} onChange={e=>setUrl(e.target.value)} disabled={busy}/></label>:<label className="studio-file"><span>{file?.name || t("选择一段视频")}</span><input type="file" aria-label={t("视频文件")} accept="video/mp4,video/webm,video/quicktime,.mkv,.avi" disabled={busy} onChange={e=>setFile(e.target.files?.[0] || null)}/><small>MP4 / MOV / MKV / WEBM / AVI</small></label>}
      <PlatformPicker value={platforms} onChange={setPlatforms} disabled={busy}/>
      {platforms.some(platform => !['bilibili', 'youtube_long', 'original'].includes(platform)) && <div className="studio-field"><span>{t('竖版版式')}</span><Select aria-label={t('竖版版式')} disabled={busy} value={options.portrait_style || 'auto'} options={[{value:'auto',label:t('按平台默认')},{value:'interview',label:t('访谈式（人物窗口）')},{value:'podcast',label:t('播客式（满屏）')}]} onChange={portrait_style=>setOptions({...options,portrait_style})}/><small>{t('仅调整竖版布局，字幕与发布文案语言仍按平台。')}</small></div>}
      <details className="studio-details"><summary>{t("有特别要求？（选填）")}</summary><label className="studio-field"><span className="studio-sr">{t("制作要求")}</span><input aria-label={t("制作要求")} placeholder={t("例如：保留完整观点或挑战过程")} maxLength={1000} value={options.instruction} disabled={busy} onChange={e=>setOptions({...options,instruction:e.target.value})}/></label></details>
      <div className="studio-row studio-import-bottom"><div><span className="studio-muted">{t('会按所选平台自动制作，数量由素材内容决定。')}</span><button className="studio-link studio-preferences-link" disabled={busy} onClick={()=>setPreferences(true)}>{t("高级偏好")}</button></div><Btn variant="cta" loading={busy} onClick={submit}>{busy?t("正在生成"):t("生成成片")}</Btn></div>
      {error&&<p className="studio-error" role="alert">{error}</p>}
    </div>
    <Dialog open={preferences} onClose={()=>setPreferences(false)} title={t("制作偏好")} description={t("默认由 AI 匹配。你指定的选项优先，生成后也可以修改。")} footer={<div className="studio-actions"><Btn onClick={()=>{setOptions({...defaultImportOptions,instruction:options.instruction});setSubtitle(null);setBrowser('')}}>{t("恢复自动")}</Btn><Btn variant="cta" onClick={()=>setPreferences(false)}>{t("完成")}</Btn></div>}>
      <ImportPreferences value={options} onChange={setOptions}/>
      <label className="studio-field">{t("已有字幕（选填）")}<input type="file" accept=".srt" aria-label={t("已有字幕")} onChange={e=>setSubtitle(e.target.files?.[0] || null)}/>{subtitle&&<small>{subtitle.name}<button className="studio-link" onClick={()=>setSubtitle(null)}>{t("移除")}</button></small>}</label>
      {source==='link'&&<details className="studio-details"><summary>{t("下载遇到登录限制时")}</summary><label className="studio-field">{t("使用浏览器登录状态")}<select value={browser} onChange={e=>setBrowser(e.target.value)}><option value="">{t("不使用")}</option>{['chrome','edge','safari','firefox'].map(b=><option key={b}>{b}</option>)}</select></label><p className="studio-muted">{t("仅在下载需要登录时选择，不会自动读取浏览器 Cookie。")}</p></details>}
    </Dialog>
  </section>
}
