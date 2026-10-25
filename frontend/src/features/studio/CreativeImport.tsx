import { trackExperience } from '../../analytics/experience'
import { useTranslation } from 'react-i18next'
import { getLocale, t } from '../../i18n'
import { useEffect, useRef, useState, type DragEvent } from 'react'
import { Select } from 'antd'
import { useNavigate } from 'react-router-dom'
import { Btn, Segmented, Dialog, StatusDot } from '../../ui'
import PlatformPicker from './PlatformPicker'
import { studioApi, errorText, errorCode } from './api'
import { trackAsrReadiness, trackAutoChoiceOverridden, trackOneClickStarted, trackOneClickUndone, trackQuickOutputPlatforms } from '../../analytics/studio'
import { telemetryId } from '../../analytics/workflow'
import { featureSnapshot, flagAssigned, flagEnabled, flagValue, useFlag } from '../../analytics/flags'
import TemplatePicker, { templateImportFields, type HtmlTemplateChoice } from './TemplatePicker'
import { OutputCaptionsSwitch } from '../settings/OutputCaptionsSetting'
import StyleProbeLine from './StyleProbeLine'
import { readStyle } from './editingStyleSession'
import { defaultImportOptions, ImportOptions } from './types'
import ImportPreferences from './ImportPreferences'
import { speechApi } from '../../services/api'
import { asrReadinessProperties, probeReadiness, repairDestination, submissionBlock, transcriptionRoute, visibleIssues, type ImportReadiness, type ReadinessIssue } from './importReadiness'
import { platformLabel } from './platformLabel'
import { readRememberedPlatforms, resolvePlatforms, samePlatforms, writeRememberedPlatforms, type PlatformSource } from './platformMemory'
import { claimBackgroundWhisperInstall, importUrlKind, isVideoFile, shouldAutoStart, shouldBackgroundInstallWhisper, UNDO_MS } from './pasteStart'
import { readImportPreferences } from './importPreferencesStore'
import TranscriptionGatePrompt from './TranscriptionGatePrompt'
import { isRecoveryCode, probeConfig, type RecoveryController } from './transcriptionRecovery'
import { SETTINGS_SAVED_EVENT } from './settingsReturn'
import { useTranscriptionRecovery } from './useTranscriptionRecovery'
import './studio.css'
import './quick-output.css'

function issueCopy(item: ReadinessIssue) {
  if (item.key === 'analysis' && item.code === 'validation_failed') return t('模型连接未通过校验。请到「设置 → 服务商与模型」按提示改密钥或地址后再生成。')
  if (item.key === 'analysis') return t('分析模型还没配好。连接一家 AI 服务后再生成。')
  if (item.code === 'whisper_installing') return t('正在安装本地转写…')
  if (item.code === 'whisper_not_installed') return t('本地转写还没安装。已有字幕可以直接继续。')
  if (item.code === 'whisper_model_missing') return t('转写模型还没下载。已有字幕可以直接继续。')
  if (item.code === 'whisper_model_downloading') return t('正在下载转写模型…')
  if (item.code === 'whisper_model_failed') return t('转写模型下载失败，请重试。已有字幕可以直接继续。')
  if (item.code === 'sensevoice_not_ready') return t('SenseVoice 还没准备好。已有字幕可以直接继续。')
  if (item.code === 'cloud_not_configured') return t('云端转写还没配好。已有字幕可以直接继续。')
  if (item.key === 'visual' && item.code === 'vision_unsupported') return t('画面理解使用的模型不能看图。请到「设置 → 服务商与模型」换一个能看图的模型后再生成。')
  if (item.key === 'visual') return t('画面分析需要可用的视觉模型。')
  if (item.key === 'ffmpeg') return t('找不到 FFmpeg，暂时无法处理视频。')
  return t('导入条件还没准备好。')
}

function repairLabel(item: ReadinessIssue) {
  if (item.repair === 'settings_ai') return item.code === 'validation_failed' ? t('去设置修改') : t('连接 AI 服务')
  if (item.repair === 'install_whisper') return item.model ? t('下载转写模型') : t('安装 Whisper')
  if (item.repair === 'settings_transcription') return t('转写设置')
  if (item.repair === 'settings_vision') return t('视觉设置')
  return ''
}


function uiLocale() {
  try { return getLocale() } catch { return 'en' }
}

const YOUTUBE_LONG_MIN_SEC = 180

function longFormNotice(durationSec: number | null, platforms: string[]) {
  const others = platforms.some(platform => platform !== 'youtube_long')
  if (durationSec != null && durationSec < YOUTUBE_LONG_MIN_SEC) {
    return others
      ? `${t('这段素材不足 3 分钟，做不了 YouTube 横屏。')} ${t('YouTube 横屏会跳过，其他平台照常生成。')}`
      : t('这段素材不足 3 分钟，做不了 YouTube 横屏。')
  }
  return others
    ? t('YouTube 横屏至少需要一条 3 分钟或更长的片段。如果素材做不出这样一条，这个版本会被跳过，其他平台仍会生成。')
    : t('YouTube 横屏至少需要一条 3 分钟或更长的片段。如果素材做不出这样一条，这个版本会被跳过。')
}

function blockMessage(reason: string, readiness?: ImportReadiness | null) {
  if (reason === 'pending') return t('正在确认导入条件…')
  if (reason === 'analysis') return readiness?.checks?.analysis?.code === 'validation_failed'
    ? t('模型连接未通过校验。请到「设置 → 服务商与模型」按提示改密钥或地址后再生成。')
    : t('请先连接 AI 服务，再导入视频。')
  if (reason === 'transcription') return t('还没有可用的转写。可以附上 SRT 字幕，或先准备好转写。')
  if (reason === 'visual') return readiness?.checks?.visual?.code === 'vision_unsupported'
    ? t('画面理解使用的模型不能看图。请到「设置 → 服务商与模型」换一个能看图的模型后再生成。')
    : t('请先配好画面分析模型，再生成成片。')
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
  const templatesOn = useFlag('pkg_templates_v1') === true
  const visualOn = useFlag('pkg_template_picker_visual') === true
  const [browser, setBrowser] = useState('')
  const [platforms, setPlatforms] = useState<string[]>(initialPlatforms.current.platforms)
  const [preferences, setPreferences] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [readiness, setReadiness] = useState<ImportReadiness | null>(null)
  const currentReadiness = readiness
  const [settled, setSettled] = useState(false)
  const [platformOpen, setPlatformOpen] = useState(false)
  const [pending, setPending] = useState<{ trigger: 'paste' | 'drop' } | null>(null)
  const [dragging, setDragging] = useState(false)
  const [longGate, setLongGate] = useState<{ open: boolean; durationSec: number | null; trigger: 'paste' | 'drop' | 'button' }>({ open: false, durationSec: null, trigger: 'button' })
  useEffect(() => {
    if (source !== 'file' || !file) {
      setLongGate(prev => prev.durationSec == null ? prev : { ...prev, durationSec: null })
      return
    }
    let cancel = false
    let objectUrl = ''
    try { objectUrl = URL.createObjectURL(file) } catch { return }
    const video = document.createElement('video')
    video.preload = 'metadata'
    const finish = (durationSec: number | null) => {
      if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = '' }
      if (!cancel) setLongGate(prev => ({ ...prev, durationSec }))
    }
    video.onloadedmetadata = () => finish(Number.isFinite(video.duration) ? video.duration : null)
    video.onerror = () => finish(null)
    video.src = objectUrl
    return () => { cancel = true; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [file, source])
  const platformSource = useRef<PlatformSource>(initialPlatforms.current.source)
  const overridden = useRef(false)
  const starting = useRef(false)
  const recoverRef = useRef<RecoveryController>(null as unknown as RecoveryController)
  const submitRef = useRef<(trigger: 'paste' | 'drop' | 'button', fresh?: ImportReadiness | null, confirmed?: boolean) => Promise<void>>(async () => {})
  const allowLink = flagEnabled('link_import_without_whisper')
  const dropZone = flagEnabled('import_drop_zone')
  const hidePreferences = flagEnabled('hide_legacy_entrypoints')
  const pasteFlag = String(flagValue('one_click_paste_start'))
  const blockOptions = { source, allowLinkWithoutWhisper: allowLink }
  useEffect(() => {
    // The first-run dialog and the settings page save through the same notification.
    // This page stays mounted across that save, so the mount probe would stay stale until reload.
    let ticket = 0
    const load = () => {
      const current = ++ticket
      studioApi.readiness()
        .then(value => {
          if (current !== ticket) return
          setReadiness(value)
          trackAsrReadiness(asrReadinessProperties(value, false))
        })
        .catch(() => { if (current === ticket) setReadiness(null) })
        .finally(() => { if (current === ticket) setSettled(true) })
    }
    load()
    window.addEventListener(SETTINGS_SAVED_EVENT, load)
    return () => { ticket += 1; window.removeEventListener(SETTINGS_SAVED_EVENT, load) }
  }, [])
  useEffect(() => {
    if (!hidePreferences) return
    const stored = readImportPreferences()
    if (stored) setOptions(current => ({ ...stored, instruction: current.instruction }))
  }, [hidePreferences])
  useEffect(() => {
    if (!shouldBackgroundInstallWhisper(allowLink, readiness?.checks?.transcription?.code)) return
    if (recoverRef.current.state.phase !== 'idle') return
    if (!claimBackgroundWhisperInstall()) return
    // #371: the background install is the controller's install too, so its polls refresh readiness and the page
    // never stays on 正在安装本地转写; the dialog stays closed unless a submit is blocked on it.
    void recoverRef.current.install({ background: true })
  }, [allowLink, readiness?.checks?.transcription?.code])
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
  const repair = async (item: ReadinessIssue) => {
    // #353: the readiness list's install button goes through the one recovery controller (no second install flow).
    if (item.repair === 'install_whisper') { resumeSubmit.current = false; setError(''); recover.open(item.code || 'whisper_not_installed', item.model); await recover.install(); return }
    if (item.repair === 'settings_ai' && blocked) { onBlocked?.(); return }
    const destination = repairDestination(item.repair)
    if (destination) navigate(destination)
  }
  // #418 rewrite: the one install-recovery controller (shared with the confirm page): install -> download ->
  // ready (continues by itself) / failed / timeout (retry or transcription settings).
  // Done waiting -> the same import continues by itself (#232); the 继续导入 button is the manual exit.
  // #349: continue with the report the controller just read, never the page's cached readiness.
  // #370: only a submit that was blocked on the install continues by itself; a download started from the list
  // (or in the background) just refreshes readiness when it finishes.
  const resumeSubmit = useRef(false)
  const recoveryDone = (report: ImportReadiness | null) => {
    if (resumeSubmit.current) { continueAfterRecovery(report); return }
    recover.close(); if (report) setReadiness(report)
  }
  const continueAfterRecovery = (report: ImportReadiness | null) => { resumeSubmit.current = false; recover.close(); setError(''); if (report) setReadiness(report); void submitRef.current?.('button', report) }
  const [recovery, recover] = useTranscriptionRecovery({ readiness: signal => studioApi.readinessProbe(signal), getRuntimeStatus: signal => speechApi.getRuntimeStatus(probeConfig(signal)), getModels: signal => speechApi.getModels(probeConfig(signal)), installRuntime: signal => speechApi.installRuntime({ signal }), downloadModel: (model, signal) => speechApi.downloadModel(model, { signal }) }, { onReady: report => recoveryDone(report), onReport: report => setReadiness(report) })
  recoverRef.current = recover
  const repairing = recovery.phase === 'installing' || recovery.phase === 'downloading'
  const changePlatforms = (next: string[]) => {
    setPlatforms(next)
    if (!next.includes('youtube_long')) setLongGate(prev => prev.open ? { ...prev, open: false } : prev)
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
  const readyToStart = (trigger: 'paste' | 'drop' | 'button', next?: { url?: string; file?: File | null }, readiness: ImportReadiness | null = currentReadiness) => {
    if (blocked) { trackExperience('import_blocked', { reason: 'setup_required', placement: 'home_setup' }); setError(t("请先连接 AI 服务，再导入视频。")); onBlocked?.(); return false }
    const nextFile = next && 'file' in next ? next.file : file
    const nextUrl = next?.url ?? url
    const nextSource = next?.file ? 'file' : next?.url ? 'link' : source
    if (nextSource === 'file' ? !nextFile : !nextUrl.trim()) { setError(t("请先添加视频文件或链接")); return false }
    const reason = submissionBlock(readiness, !!subtitle, settled, { source: nextSource, allowLinkWithoutWhisper: allowLink })
    if (reason === 'pending') { setError(blockMessage(reason, readiness)); return false }
    trackAsrReadiness(asrReadinessProperties(readiness, !!subtitle))
    const check = readiness?.checks?.transcription
    if (reason === 'transcription' && nextSource === 'file' && !subtitle && !check?.skippable && isRecoveryCode(check?.code)) {
      setError(''); resumeSubmit.current = true; recover.open(check!.code, check!.model); return false
    }
    if (reason) { setError(blockMessage(reason, readiness)); return false }
    if (trigger !== 'button') setError('')
    return true
  }
  const arm = (trigger: 'paste' | 'drop', next: { url?: string; file?: File }) => {
    // drop, global paste and the file picker all come through here; while a submit is running
    // (including its readiness re-check) the source is locked, so what is shown is what gets uploaded.
    if (starting.current) return
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
  const submit = async (trigger: 'paste' | 'drop' | 'button' = 'button', fresh?: ImportReadiness | null, confirmed = false) => {
    if (starting.current) return
    if (trigger === 'button') setPending(null)
    if (platforms.includes('youtube_long') && !confirmed) {
      if (!readyToStart(trigger, undefined, fresh ?? readiness)) return
      setLongGate(prev => ({ ...prev, open: true, trigger }))
      return
    }
    // one busy state from the click on. The re-probe below can wait, and the inputs stay locked
    // (busy disables them) so the request carries exactly what the user saw when they clicked.
    starting.current = true
    setBusy(true)
    try {
      let report = fresh ?? readiness
      if (settled && !report) {
        // (PM): re-check up to 3 times; still unknown -> send the import and let the backend gate answer (422).
        report = await probeReadiness(() => studioApi.readiness())
        if (report) setReadiness(report)
      }
      if (!readyToStart(trigger, undefined, report)) return
      setError('')
      const flowId = telemetryId()
      const body = new FormData()
      body.append('goal', options.goal); body.append('language', options.language); body.append('instruction', options.instruction)
      platforms.forEach(platform => body.append('platforms', platform))
      body.append('auto_start', 'true')
      body.append('portrait_style', options.portrait_style || 'auto')
      const portraitChosen = platforms.some(platform => !['bilibili', 'youtube_long', 'original'].includes(platform))
      const styleKey = templatesOn && visualOn && portraitChosen ? (source === 'file' ? (file ? `file:${file.name}:${file.size}:${file.lastModified}` : null) : (url.trim() ? `url:${url.trim()}` : null)) : null
      const recommendation = visualOn && styleKey && readStyle().key === styleKey ? readStyle().result?.template : undefined
      const templateFields = templateImportFields(templatesOn, options.html_template, recommendation)
      if (templateFields.html_template) body.append('html_template', templateFields.html_template)
      if (templateFields.recommended_template) body.append('recommended_template', templateFields.recommended_template)
      body.append('features', JSON.stringify(featureSnapshot()))
      if (options.aspect) body.append('aspect', options.aspect)
      if (options.duration) body.append('duration', String(options.duration))
      if (subtitle) body.append('subtitle', subtitle)
      body.append('name', file && source === 'file' ? file.name.replace(/\.[^.]+$/, '') : t("智能剪辑"))
      if (source === 'file' && file) body.append('video', file)
      else { body.append('url', url.trim()); if (browser) body.append('browser', browser) }
      body.append('features', JSON.stringify(featureSnapshot()))
      body.append('flow_id', flowId)
      const skippedWhisper = allowLink && source !== 'file' && !!readiness && !readiness?.checks?.transcription?.ok && !subtitle
      const result = await studioApi.import(body)
      trackOneClickStarted({
        trigger, flow_id: flowId, platform_count: platforms.length, platform_source: platformSource.current,
        has_subtitle: !!subtitle, transcription_route: transcriptionRoute({ hasSubtitle: !!subtitle, code: readiness?.checks?.transcription?.code, skippedWhisper }),
      }, flagAssigned('one_click_paste_start') || flagAssigned('remember_platforms') || flagAssigned('link_import_without_whisper') || flagAssigned('import_drop_zone'))
      trackQuickOutputPlatforms({ platform_count: platforms.length, portrait_style: options.portrait_style || 'auto' })
      if (remembered) writeRememberedPlatforms(platforms)
      // Project refresh should never make a successful import look like an upload failure.
      void onImported().catch(() => undefined)
      navigate(`/project/${result.project_id}`)
    } catch (e) {
      // the backend gate sends a stable code; the prompt is chosen from it, never from the text.
      const code = errorCode(e)
      if (isRecoveryCode(code)) { setError(''); resumeSubmit.current = true; recover.open(code as string, readiness?.checks?.transcription?.model) }
      else setError(t(errorText(e)))  // includes coded source refusals (source_unreadable ...): shown at once
    } finally { starting.current = false; setBusy(false) }
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
  const youtubeLongOnlyTooShort = longGate.durationSec != null && longGate.durationSec < YOUTUBE_LONG_MIN_SEC && platforms.length > 0 && platforms.every(platform => platform === 'youtube_long')
  return <section className="ac-creative-import">
    <h1 className="ac-title">{t("放入视频，直接生成可发布成片。")}</h1>
    <p className="studio-muted">{t("选择发布平台，AI 会自动挑选内容、完成剪辑与渲染。生成后可直接下载或继续编辑。")}</p>
    <div className="studio-import-box">
      {dropZone ? <div className={`ac-dropzone${dragging ? ' is-hot' : ''}`} onDragEnter={event => { event.preventDefault(); setDragging(true) }} onDragOver={event => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
        <p className="ac-dropzone-title">{t('把链接或视频放在这里')}</p>
        <p className="ac-dropzone-hint">{t('粘贴链接，或拖入一个视频文件。')}</p>
        <label className="studio-field ac-dropzone-field"><span className="studio-sr">{t("视频链接")}</span><textarea placeholder={t("粘贴 B 站或 YouTube 视频链接")} value={url} onChange={event => { setPending(null); setUrl(event.target.value); if (event.target.value) { setFile(null); setSource('link') } }} disabled={busy}/></label>
        {file && <p className="ac-dropzone-file"><span>{file.name}</span><button type="button" className="studio-link" disabled={busy} onClick={() => setFile(null)}>{t('移除')}</button></p>}
        <label className="studio-link ac-dropzone-file-label">{t('选择一个视频文件')}<input type="file" aria-label={t("视频文件")} accept="video/mp4,video/webm,video/quicktime,.mkv,.avi" disabled={busy} onChange={event => { const picked = event.target.files?.[0] || null; if (picked) arm('drop', { file: picked }) }}/></label>
      </div> : <>
        <div className="studio-row"><Segmented ariaLabel={t("导入来源")} value={source} onChange={v=>!busy&&setSource(v)} options={[{value:'link',label:t("链接导入")},{value:'file',label:t("文件导入")}]}/></div>
        {source==='link'?<label className="studio-field"><span className="studio-sr">{t("视频链接")}</span><textarea placeholder={t("粘贴 B 站或 YouTube 视频链接")} value={url} onChange={e=>setUrl(e.target.value)} onPaste={event => { const text = event.clipboardData.getData('text'); if (importUrlKind(text) && shouldAutoStart(pasteFlag, 'paste')) { event.preventDefault(); arm('paste', { url: text.trim() }) } }} disabled={busy}/></label>:<label className="studio-file"><span>{file?.name || t("选择一段视频")}</span><input type="file" aria-label={t("视频文件")} accept="video/mp4,video/webm,video/quicktime,.mkv,.avi" disabled={busy} onChange={e=>{ const picked = e.target.files?.[0] || null; setFile(picked); if (picked) arm('drop', { file: picked }) }}/><small>MP4 / MOV / MKV / WEBM / AVI</small></label>}
      </>}
      {templatesOn && visualOn && platforms.some(platform => !['bilibili', 'youtube_long', 'original'].includes(platform)) && <StyleProbeLine sourceKey={source === 'file' ? (file ? `file:${file.name}:${file.size}:${file.lastModified}` : null) : (url.trim() ? `url:${url.trim()}` : null)} />}
      {remembered ? <div className="ac-platform-line"><p>{t('为 {{names}} 制作', { names })}</p><button type="button" className="studio-link" disabled={busy} onClick={() => setPlatformOpen(open => !open)}>{t('改')}</button></div> : null}
      {(!remembered || platformOpen) && <PlatformPicker value={platforms} onChange={changePlatforms} disabled={busy}/>}
      {templatesOn && platforms.some(platform => !['bilibili', 'youtube_long', 'original'].includes(platform)) && <TemplatePicker visual={visualOn} disabled={busy} value={options.html_template} sourceKey={source === 'file' ? (file ? `file:${file.name}:${file.size}:${file.lastModified}` : null) : (url.trim() ? `url:${url.trim()}` : null)} url={url} file={file} sourceKind={source === 'file' ? (file ? 'file' : 'none') : (url.trim() ? 'link' : 'none')} onChange={(html_template: HtmlTemplateChoice) => setOptions({...options, html_template})}/>}
      {!templatesOn && platforms.some(platform => !['bilibili', 'youtube_long', 'original'].includes(platform)) && <div className="studio-field"><span>{t('竖版版式')}</span><Select aria-label={t('竖版版式')} disabled={busy} value={options.portrait_style || 'auto'} options={[{value:'auto',label:t('按平台默认')},{value:'interview',label:t('访谈式（人物窗口）')},{value:'podcast',label:t('播客式（满屏）')}]} onChange={portrait_style=>setOptions({...options,portrait_style})}/><small>{t('仅调整竖版布局，字幕与发布文案语言仍按平台。')}</small></div>}
      {templatesOn && options.html_template === 'classic' && platforms.some(platform => !['bilibili', 'youtube_long', 'original'].includes(platform)) && <div className="studio-field"><span>{t('竖版版式')}</span><Select aria-label={t('竖版版式')} disabled={busy} value={options.portrait_style || 'auto'} options={[{value:'auto',label:t('按平台默认')},{value:'interview',label:t('访谈式（人物窗口）')},{value:'podcast',label:t('播客式（满屏）')}]} onChange={portrait_style=>setOptions({...options,portrait_style})}/><small>{t('仅调整竖版布局，字幕与发布文案语言仍按平台。')}</small></div>}
      <OutputCaptionsSwitch label={t('字幕')} hint={t('关闭后成片不带字幕。标题只在封面上，不会烧进视频。')} />
      <details className="studio-details"><summary>{t("有特别要求？（选填）")}</summary><label className="studio-field"><span className="studio-sr">{t("制作要求")}</span><input aria-label={t("制作要求")} placeholder={t("例如：保留完整观点或挑战过程")} maxLength={1000} value={options.instruction} disabled={busy} onChange={e=>setOptions({...options,instruction:e.target.value})}/></label></details>
      {issues.length > 0 && <div className="studio-readiness" role="status">
        {issues.map(item => <div className="studio-readiness-row" key={item.key}>
          <StatusDot tone={item.code === 'whisper_installing' || item.code === 'whisper_model_downloading' ? 'accent' : 'muted'} label={issueCopy(item)} />
          {item.repair !== 'none' && <Btn size="sm" disabled={busy || repairing} loading={repairing && item.repair === 'install_whisper'} onClick={() => void repair(item)}>{repairLabel(item)}</Btn>}
        </div>)}
      </div>}
      {platforms.includes('youtube_long') && <p className="studio-muted" role="note">{longFormNotice(longGate.durationSec, platforms)}</p>}
      {pending && <div className="ac-undo" role="status"><span>{t('即将开始制作。')}</span><button type="button" className="ac-undo-action" onClick={undo}>{t('撤销')}</button></div>}
      <div className="studio-row studio-import-bottom"><div><span className="studio-muted">{t('会按所选平台自动制作，数量由素材内容决定。')}</span>{!hidePreferences && <button className="studio-link studio-preferences-link" disabled={busy} onClick={()=>setPreferences(true)}>{t("高级偏好")}</button>}</div><Btn variant="cta" loading={busy} onClick={() => submit('button')}>{busy?t("正在生成"):t("生成成片")}</Btn></div>
      <TranscriptionGatePrompt state={recovery} busy={busy} onInstall={() => recover.install()} onRetry={() => recover.retry()} onContinue={() => continueAfterRecovery(null)} navigate={navigate}/>
      {error&&<p className="studio-error" role="alert">{error}</p>}
    </div>
    <Dialog open={preferences} onClose={()=>setPreferences(false)} title={t("制作偏好")} description={t("默认由 AI 匹配。你指定的选项优先，生成后也可以修改。")} footer={<div className="studio-actions"><Btn onClick={()=>{setOptions({...defaultImportOptions,instruction:options.instruction});setSubtitle(null);setBrowser('')}}>{t("恢复自动")}</Btn><Btn variant="cta" onClick={()=>setPreferences(false)}>{t("完成")}</Btn></div>}>
      <ImportPreferences value={options} onChange={setOptions}/>
      <label className="studio-field">{t("已有字幕（选填）")}<input type="file" accept=".srt" aria-label={t("已有字幕")} onChange={e=>setSubtitle(e.target.files?.[0] || null)}/>{subtitle&&<small>{subtitle.name}<button className="studio-link" onClick={()=>setSubtitle(null)}>{t("移除")}</button></small>}</label>
      {source==='link'&&<details className="studio-details"><summary>{t("下载遇到登录限制时")}</summary><label className="studio-field">{t("使用浏览器登录状态")}<select value={browser} onChange={e=>setBrowser(e.target.value)}><option value="">{t("不使用")}</option>{['chrome','edge','safari','firefox'].map(b=><option key={b}>{b}</option>)}</select></label><p className="studio-muted">{t("仅在下载需要登录时选择，不会自动读取浏览器 Cookie。")}</p></details>}
    </Dialog>
    <Dialog open={longGate.open} onClose={() => setLongGate(prev => ({ ...prev, open: false }))} title={t('YouTube 横屏')} description={youtubeLongOnlyTooShort ? <>{longFormNotice(longGate.durationSec, platforms)} {t('请再选一个其他平台。')}</> : longFormNotice(longGate.durationSec, platforms)} footer={youtubeLongOnlyTooShort ? <div className="studio-actions"><Btn onClick={() => setLongGate(prev => ({ ...prev, open: false }))}>{t('知道了')}</Btn></div> : <div className="studio-actions"><Btn onClick={() => setLongGate(prev => ({ ...prev, open: false }))}>{t('取消')}</Btn><Btn variant="cta" onClick={() => { const trigger = longGate.trigger || 'button'; setLongGate(prev => ({ ...prev, open: false })); void submit(trigger, undefined, true) }}>{t('确认并开始')}</Btn></div>} />
  </section>
}
