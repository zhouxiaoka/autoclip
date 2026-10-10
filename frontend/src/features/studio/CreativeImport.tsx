import { trackExperience } from '../../analytics/experience'
import { useTranslation } from 'react-i18next'
import { getLocale, t } from '../../i18n'
import { useEffect, useRef, useState, type DragEvent } from 'react'
import { Select } from 'antd'
import { useNavigate } from 'react-router-dom'
import { Btn, Segmented, Dialog, StatusDot } from '../../ui'
import PlatformPicker from './PlatformPicker'
import { studioApi, errorText } from './api'
import { trackAutoChoiceOverridden, trackOneClickStarted, trackOneClickUndone, trackQuickOutputPlatforms } from '../../analytics/studio'
import { telemetryId } from '../../analytics/workflow'
import { featureSnapshot, flagAssigned, flagEnabled, flagValue, useFlag } from '../../analytics/flags'
import TemplatePicker, { templateImportFields, type HtmlTemplateChoice } from './TemplatePicker'
import { readStyle } from './editingStyleSession'
import { defaultImportOptions, ImportOptions } from './types'
import ImportPreferences from './ImportPreferences'
import { speechApi } from '../../services/api'
import { repairDestination, submissionBlock, transcriptionRoute, visibleIssues, type ImportReadiness, type ReadinessIssue } from './importReadiness'
import { platformLabel } from './platformLabel'
import { readRememberedPlatforms, resolvePlatforms, samePlatforms, writeRememberedPlatforms, type PlatformSource } from './platformMemory'
import { claimBackgroundWhisperInstall, importUrlKind, isVideoFile, shouldAutoStart, shouldBackgroundInstallWhisper, UNDO_MS } from './pasteStart'
import { readImportPreferences } from './importPreferencesStore'
import './studio.css'
import './quick-output.css'

function issueCopy(item: ReadinessIssue) {
  if (item.key === 'analysis') return t('分析模型还没配好。连接一家 AI 服务后再生成。')
  if (item.code === 'whisper_installing') return t('正在安装本地转写…')
  if (item.code === 'whisper_not_installed') return t('本地转写还没安装。已有字幕可以直接继续。')
  if (item.code === 'whisper_model_missing') return t('转写模型还没下载。已有字幕可以直接继续。')
  if (item.code === 'whisper_model_downloading') return t('正在下载转写模型…')
  if (item.code === 'whisper_model_failed') return t('转写模型下载失败，请重试。已有字幕可以直接继续。')
  if (item.code === 'sensevoice_not_ready') return t('SenseVoice 还没准备好。已有字幕可以直接继续。')
  if (item.code === 'cloud_not_configured') return t('云端转写还没配好。已有字幕可以直接继续。')
  if (item.key === 'visual') return t('画面分析需要可用的视觉模型。')
  if (item.key === 'ffmpeg') return t('找不到 FFmpeg，暂时无法处理视频。')
  return t('导入条件还没准备好。')
}

function repairLabel(item: ReadinessIssue) {
  if (item.repair === 'settings_ai') return t('连接 AI 服务')
  if (item.repair === 'install_whisper') return item.model ? t('下载转写模型') : t('安装 Whisper')
  if (item.repair === 'settings_transcription') return t('转写设置')
  if (item.repair === 'settings_vision') return t('视觉设置')
  return ''
}

function uiLocale() {
  try { return getLocale() } catch { return 'en' }
}

function blockMessage(reason: string) {
  if (reason === 'pending') return t('正在确认导入条件…')
  if (reason === 'analysis') return t('请先连接 AI 服务，再导入视频。')
  if (reason === 'transcription') return t('还没有可用的转写。可以附上 SRT 字幕，或先准备好转写。')
  if (reason === 'visual') return t('请先配好画面分析模型，再生成成片。')
  if (reason === 'ffmpeg') return t('找不到 FFmpeg，无法生成成片。')
  return ''
}

export default function CreativeImport({ onImported, blocked = false, onBlocked }: { onImported: () => Promise<void>; blocked?: boolean; onBlocked?: () => void }) {
  useTranslation()
  const navigate = useNavigate()
  const remembered = flagEnabled('remember_platforms')
  const initialPlatforms = useRef(resolvePlatforms(remembered, uiLocale(), readRememberedPlatforms()))
  const [source, setSource] = useState<'link' | 'file'>('link')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [subtitle, setSubtitle] = useState<File | null>(null)
  const [options, setOptions] = useState<ImportOptions>({...defaultImportOptions})
  const [browser, setBrowser] = useState('')
  const [platforms, setPlatforms] = useState<string[]>(initialPlatforms.current.platforms)
  const [preferences, setPreferences] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [readiness, setReadiness] = useState<ImportReadiness | null>(null)
  const [settled, setSettled] = useState(false)
  const [repairing, setRepairing] = useState(false)
  const [platformOpen, setPlatformOpen] = useState(false)
  const [pending, setPending] = useState<{ trigger: 'paste' | 'drop' } | null>(null)
  const [dragging, setDragging] = useState(false)
  const platformSource = useRef<PlatformSource>(initialPlatforms.current.source)
  const overridden = useRef(false)
  const starting = useRef(false)
  const submitRef = useRef<(trigger: 'paste' | 'drop' | 'button') => Promise<void>>(async () => {})
  // Installing the runtime is only half of local transcription: download the model right after.
  const modelAfterRuntime = useRef(false)
  const allowLink = flagEnabled('link_import_without_whisper')
  const dropZone = flagEnabled('import_drop_zone')
  const hidePreferences = flagEnabled('hide_legacy_entrypoints')
  const pasteFlag = String(flagValue('one_click_paste_start'))
  const templatesOn = useFlag('pkg_templates_v1') === true
  const visualOn = useFlag('pkg_template_picker_visual') === true
  const blockOptions = { source, allowLinkWithoutWhisper: allowLink }
  const portraitChosen = platforms.some(platform => !['bilibili', 'youtube_long', 'original'].includes(platform))
  const sourceKey = source === 'file' ? (file ? `file:${file.name}:${file.size}:${file.lastModified}` : null) : (url.trim() ? `url:${url.trim()}` : null)
  const sourceKind: 'link' | 'file' | 'none' = source === 'file' ? (file ? 'file' : 'none') : (url.trim() ? 'link' : 'none')
  useEffect(() => {
    let cancel = false
    studioApi.readiness()
      .then(value => { if (!cancel) setReadiness(value) })
      .catch(() => { if (!cancel) setReadiness(null) })
      .finally(() => { if (!cancel) setSettled(true) })
    return () => { cancel = true }
  }, [])
  useEffect(() => {
    if (!hidePreferences) return
    const stored = readImportPreferences()
    if (stored) setOptions(current => ({ ...stored, instruction: current.instruction }))
  }, [hidePreferences])
  useEffect(() => {
    const check = readiness?.checks.transcription
    if (check?.code === 'whisper_model_missing' && check.model && modelAfterRuntime.current) {
      modelAfterRuntime.current = false
      void downloadModel(check.model)
      return
    }
    if (check?.code === 'whisper_install_failed') modelAfterRuntime.current = false
    if (check?.code !== 'whisper_installing' && check?.code !== 'whisper_model_downloading') return
    const timer = window.setInterval(() => {
      studioApi.readiness().then(setReadiness).catch(() => undefined)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [readiness?.checks.transcription.code])
  useEffect(() => {
    if (!shouldBackgroundInstallWhisper(allowLink, readiness?.checks.transcription.code)) return
    if (!claimBackgroundWhisperInstall()) return
    void speechApi.installRuntime()
      .then(() => studioApi.readiness().then(setReadiness).catch(() => undefined))
      .catch(() => undefined)
  }, [allowLink, readiness?.checks.transcription.code])
  useEffect(() => {
    if (!pending) return
    const timer = window.setTimeout(() => {
      const trigger = pending.trigger
      setPending(null)
      void submitRef.current(trigger)
    }, UNDO_MS)
    return () => window.clearTimeout(timer)
  }, [pending])
  useEffect(() => {
    if (pasteFlag !== 'autostart' && !dropZone) return
    const onPaste = (event: ClipboardEvent) => {
      const target = event.target
      if (target instanceof HTMLElement && target.closest('input, textarea, [contenteditable="true"]') && !target.closest('.ac-creative-import')) return
      const text = event.clipboardData?.getData('text') || ''
      if (!importUrlKind(text) || !shouldAutoStart(pasteFlag, 'paste')) return
      event.preventDefault()
      arm('paste', { url: text.trim() })
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [pasteFlag, dropZone, busy, settled, allowLink, source])
  const issues = visibleIssues(readiness, !!subtitle, blockOptions)
  const downloadModel = async (model: string) => {
    setRepairing(true)
    setError('')
    try {
      await speechApi.downloadModel(model)
      setReadiness(await studioApi.readiness())
      setSettled(true)
    } catch (e) { setError(t(errorText(e))) } finally { setRepairing(false) }
  }
  const repair = async (item: ReadinessIssue) => {
    if (item.repair === 'install_whisper' && item.model) { await downloadModel(item.model); return }
    if (item.repair === 'install_whisper') {
      modelAfterRuntime.current = true
      setRepairing(true)
      setError('')
      try {
        await speechApi.installRuntime()
        setReadiness(await studioApi.readiness())
        setSettled(true)
      } catch (e) { modelAfterRuntime.current = false; setError(t(errorText(e))) } finally { setRepairing(false) }
      return
    }
    if (item.repair === 'settings_ai' && blocked) { onBlocked?.(); return }
    const destination = repairDestination(item.repair)
    if (destination) navigate(destination)
  }
  const changePlatforms = (next: string[]) => {
    setPlatforms(next)
    if (remembered) writeRememberedPlatforms(next)
    else platformSource.current = 'user'
    if (samePlatforms(next, initialPlatforms.current.platforms)) return
    platformSource.current = 'user'
    if (overridden.current) return
    // One event if either flag is assigned, so remembering and override tracking do not double count.
    if (!(flagAssigned('remember_platforms') || flagAssigned('track_overrides'))) return
    overridden.current = true
    trackAutoChoiceOverridden({ field: 'platform', stage: 'pre_import' }, true)
  }
  const readyToStart = (trigger: 'paste' | 'drop' | 'button', next?: { url?: string; file?: File | null }) => {
    if (blocked) { trackExperience('import_blocked', { reason: 'setup_required', placement: 'home_setup' }); setError(t("请先连接 AI 服务，再导入视频。")); onBlocked?.(); return false }
    const nextFile = next && 'file' in next ? next.file : file
    const nextUrl = next?.url ?? url
    const nextSource = next?.file ? 'file' : next?.url ? 'link' : source
    if (nextSource === 'file' ? !nextFile : !nextUrl.trim()) { setError(t("请先添加视频文件或链接")); return false }
    const reason = submissionBlock(readiness, !!subtitle, settled, { source: nextSource, allowLinkWithoutWhisper: allowLink })
    if (reason) { setError(blockMessage(reason)); return false }
    if (trigger !== 'button') setError('')
    return true
  }
  const arm = (trigger: 'paste' | 'drop', next: { url?: string; file?: File }) => {
    if (next.file) { setFile(next.file); setUrl(''); setSource('file') }
    else if (next.url) { setUrl(next.url); setFile(null); setSource('link') }
    if (!shouldAutoStart(pasteFlag, trigger)) return
    if (!readyToStart(trigger, next)) return
    setPending({ trigger })
  }
  const undo = () => {
    const trigger = pending?.trigger
    setPending(null)
    if (trigger) trackOneClickUndone({ trigger }, flagAssigned('one_click_paste_start'))
  }
  const submit = async (trigger: 'paste' | 'drop' | 'button' = 'button') => {
    if (starting.current) return
    if (trigger === 'button') setPending(null)
    if (!readyToStart(trigger)) return
    starting.current = true
    setBusy(true); setError('')
    try {
      const flowId = telemetryId()
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
      const styleKey = templatesOn && visualOn && portraitChosen ? sourceKey : null
      const recommendation = visualOn && styleKey && readStyle().key === styleKey ? readStyle().result?.template : undefined
      const templateFields = templateImportFields(templatesOn, options.html_template, recommendation)
      if (templateFields.html_template) body.append('html_template', templateFields.html_template)
      if (templateFields.recommended_template) body.append('recommended_template', templateFields.recommended_template)
      body.append('features', JSON.stringify(featureSnapshot()))
      body.append('flow_id', flowId)
      const skippedWhisper = allowLink && source !== 'file' && !!readiness && !readiness.checks.transcription.ok && !subtitle
      const result = await studioApi.import(body)
      trackOneClickStarted({
        trigger, flow_id: flowId, platform_count: platforms.length, platform_source: platformSource.current,
        has_subtitle: !!subtitle, transcription_route: transcriptionRoute({ hasSubtitle: !!subtitle, code: readiness?.checks.transcription.code, skippedWhisper }),
      }, flagAssigned('one_click_paste_start') || flagAssigned('remember_platforms') || flagAssigned('link_import_without_whisper') || flagAssigned('import_drop_zone'))
      trackQuickOutputPlatforms({ platform_count: platforms.length, portrait_style: options.portrait_style || 'auto' })
      if (remembered) writeRememberedPlatforms(platforms)
      // Project refresh should never make a successful import look like an upload failure.
      void onImported().catch(() => undefined)
      navigate(`/project/${result.project_id}`)
    } catch (e) { setError(t(errorText(e))) } finally { starting.current = false; setBusy(false) }
  }
  submitRef.current = submit
  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragging(false)
    const dropped = [...event.dataTransfer.files].find(item => isVideoFile(item))
    if (dropped) { arm('drop', { file: dropped }); return }
    const text = event.dataTransfer.getData('text/uri-list') || event.dataTransfer.getData('text/plain')
    if (importUrlKind(text)) arm('paste', { url: text.trim() })
  }
  const names = platforms.map(platformLabel).join(uiLocale().toLowerCase().startsWith('zh') ? '、' : ', ')
  return <section className="ac-creative-import">
    <h1 className="ac-title">{t("放入视频，直接生成可发布成片。")}</h1>
    <p className="studio-muted">{t("选择发布平台，AI 会自动挑选内容、完成剪辑与渲染。生成后可直接下载或继续编辑。")}</p>
    <div className="studio-import-box">
      {dropZone ? <div className={`ac-dropzone${dragging ? ' is-hot' : ''}`} onDragEnter={event => { event.preventDefault(); setDragging(true) }} onDragOver={event => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
        <p className="ac-dropzone-title">{t('把链接或视频放在这里')}</p>
        <p className="ac-dropzone-hint">{t('粘贴链接，或拖入一个视频文件。')}</p>
        <label className="studio-field ac-dropzone-field"><span className="studio-sr">{t("视频链接")}</span><textarea placeholder={t("粘贴 B 站或 YouTube 视频链接")} value={url} onChange={event => { setPending(null); setUrl(event.target.value); if (event.target.value) { setFile(null); setSource('link') } }} disabled={busy}/></label>
        {file && <p className="ac-dropzone-file"><span>{file.name}</span><button type="button" className="studio-link" onClick={() => setFile(null)}>{t('移除')}</button></p>}
        <label className="studio-link ac-dropzone-file-label">{t('选择一个视频文件')}<input type="file" aria-label={t("视频文件")} accept="video/mp4,video/webm,video/quicktime,.mkv,.avi" disabled={busy} onChange={event => { const picked = event.target.files?.[0] || null; if (picked) arm('drop', { file: picked }) }}/></label>
      </div> : <>
        <div className="studio-row"><Segmented ariaLabel={t("导入来源")} value={source} onChange={v=>!busy&&setSource(v)} options={[{value:'link',label:t("链接导入")},{value:'file',label:t("文件导入")}]}/></div>
        {source==='link'?<label className="studio-field"><span className="studio-sr">{t("视频链接")}</span><textarea placeholder={t("粘贴 B 站或 YouTube 视频链接")} value={url} onChange={e=>setUrl(e.target.value)} onPaste={event => { const text = event.clipboardData.getData('text'); if (importUrlKind(text) && shouldAutoStart(pasteFlag, 'paste')) { event.preventDefault(); arm('paste', { url: text.trim() }) } }} disabled={busy}/></label>:<label className="studio-file"><span>{file?.name || t("选择一段视频")}</span><input type="file" aria-label={t("视频文件")} accept="video/mp4,video/webm,video/quicktime,.mkv,.avi" disabled={busy} onChange={e=>{ const picked = e.target.files?.[0] || null; setFile(picked); if (picked) arm('drop', { file: picked }) }}/><small>MP4 / MOV / MKV / WEBM / AVI</small></label>}
      </>}
      {remembered ? <div className="ac-platform-line"><p>{t('为 {{names}} 制作', { names })}</p><button type="button" className="studio-link" disabled={busy} onClick={() => setPlatformOpen(open => !open)}>{t('改')}</button></div> : null}
      {(!remembered || platformOpen) && <PlatformPicker value={platforms} onChange={changePlatforms} disabled={busy}/>}
      {templatesOn && portraitChosen && <TemplatePicker visual={visualOn} disabled={busy} value={options.html_template} sourceKey={sourceKey} url={url} file={file} sourceKind={sourceKind} onChange={(html_template: HtmlTemplateChoice) => setOptions({...options, html_template})}/>}
      {!templatesOn && portraitChosen && <div className="studio-field"><span>{t('竖版版式')}</span><Select aria-label={t('竖版版式')} disabled={busy} value={options.portrait_style || 'auto'} options={[{value:'auto',label:t('按平台默认')},{value:'interview',label:t('访谈式（人物窗口）')},{value:'podcast',label:t('播客式（满屏）')}]} onChange={portrait_style=>setOptions({...options,portrait_style})}/><small>{t('仅调整竖版布局，字幕与发布文案语言仍按平台。')}</small></div>}
      {templatesOn && options.html_template === 'classic' && portraitChosen && <div className="studio-field"><span>{t('竖版版式')}</span><Select aria-label={t('竖版版式')} disabled={busy} value={options.portrait_style || 'auto'} options={[{value:'auto',label:t('按平台默认')},{value:'interview',label:t('访谈式（人物窗口）')},{value:'podcast',label:t('播客式（满屏）')}]} onChange={portrait_style=>setOptions({...options,portrait_style})}/><small>{t('仅调整竖版布局，字幕与发布文案语言仍按平台。')}</small></div>}
      <details className="studio-details"><summary>{t("有特别要求？（选填）")}</summary><label className="studio-field"><span className="studio-sr">{t("制作要求")}</span><input aria-label={t("制作要求")} placeholder={t("例如：保留完整观点或挑战过程")} maxLength={1000} value={options.instruction} disabled={busy} onChange={e=>setOptions({...options,instruction:e.target.value})}/></label></details>
      {issues.length > 0 && <div className="studio-readiness" role="status">
        {issues.map(item => <div className="studio-readiness-row" key={item.key}>
          <StatusDot tone={item.code === 'whisper_installing' || item.code === 'whisper_model_downloading' ? 'accent' : 'muted'} label={issueCopy(item)} />
          {item.repair !== 'none' && <Btn size="sm" disabled={busy || repairing} loading={repairing && item.repair === 'install_whisper'} onClick={() => void repair(item)}>{repairLabel(item)}</Btn>}
        </div>)}
      </div>}
      {pending && <div className="ac-undo" role="status"><span>{t('即将开始制作。')}</span><button type="button" className="ac-undo-action" onClick={undo}>{t('撤销')}</button></div>}
      <div className="studio-row studio-import-bottom"><div><span className="studio-muted">{t('会按所选平台自动制作，数量由素材内容决定。')}</span>{!hidePreferences && <button className="studio-link studio-preferences-link" disabled={busy} onClick={()=>setPreferences(true)}>{t("高级偏好")}</button>}</div><Btn variant="cta" loading={busy} onClick={() => submit('button')}>{busy?t("正在生成"):t("生成成片")}</Btn></div>
      {error&&<p className="studio-error" role="alert">{error}</p>}
    </div>
    <Dialog open={preferences} onClose={()=>setPreferences(false)} title={t("制作偏好")} description={t("默认由 AI 匹配。你指定的选项优先，生成后也可以修改。")} footer={<div className="studio-actions"><Btn onClick={()=>{setOptions({...defaultImportOptions,instruction:options.instruction});setSubtitle(null);setBrowser('')}}>{t("恢复自动")}</Btn><Btn variant="cta" onClick={()=>setPreferences(false)}>{t("完成")}</Btn></div>}>
      <ImportPreferences value={options} onChange={setOptions}/>
      <label className="studio-field">{t("已有字幕（选填）")}<input type="file" accept=".srt" aria-label={t("已有字幕")} onChange={e=>setSubtitle(e.target.files?.[0] || null)}/>{subtitle&&<small>{subtitle.name}<button className="studio-link" onClick={()=>setSubtitle(null)}>{t("移除")}</button></small>}</label>
      {source==='link'&&<details className="studio-details"><summary>{t("下载遇到登录限制时")}</summary><label className="studio-field">{t("使用浏览器登录状态")}<select value={browser} onChange={e=>setBrowser(e.target.value)}><option value="">{t("不使用")}</option>{['chrome','edge','safari','firefox'].map(b=><option key={b}>{b}</option>)}</select></label><p className="studio-muted">{t("仅在下载需要登录时选择，不会自动读取浏览器 Cookie。")}</p></details>}
    </Dialog>
  </section>
}
