import { trackExperience } from '../../analytics/experience'
import { useTranslation } from 'react-i18next'
import { getLocale, t } from '../../i18n'
import { useEffect, useRef, useState, type DragEvent, type Ref } from 'react'
import { Select } from 'antd'
import { useNavigate } from 'react-router-dom'
import { Btn, Segmented, Dialog, StatusDot } from '../../ui'
import PlatformPicker from './PlatformPicker'
import type { ChannelReplay } from './ChannelReplays'
import LiveReplayPicker, { type RemoteReplay, type ReplayFileSource } from './LiveReplayPicker'
import { studioApi, errorText, errorCode } from './api'
import { trackAsrReadiness, trackAutoChoiceOverridden, trackImportPreviewShown, trackOneClickStarted, trackOneClickUndone, trackQuickOutputPlatforms } from '../../analytics/studio'
import { telemetryId } from '../../analytics/workflow'
import { featureSnapshot, flagAssigned, flagEnabled, flagValue, useFlag } from '../../analytics/flags'
import TemplatePicker, { templateImportFields, type HtmlTemplateChoice } from './TemplatePicker'
import { OutputCaptionsSwitch } from '../settings/OutputCaptionsSetting'
import StyleProbeLine from './StyleProbeLine'
import { readStyle } from './editingStyleSession'
import { defaultImportOptions, FIRST_WINDOW_END_SEC, ImportOptions } from './types'
import ImportPreferences from './ImportPreferences'
import { speechApi } from '../../services/api'
import { CLOUD_TRANSCRIPTION_DESTINATION, analysisNeedsSetup, asrReadinessProperties, durationBucket, probeReadiness, repairDestination, submissionBlock, transcriptionRoute, visibleIssues, type ImportReadiness, type ReadinessCheck, type ReadinessIssue } from './importReadiness'
import ImportSetupCard from './ImportSetupCard'
import { platformLabel } from './platformLabel'
import { hasSuccessHistory, readRememberedPlatforms, resolvePlatforms, samePlatforms, takeReuseImport, writeRememberedPlatforms, type PlatformSource } from './platformMemory'
import { claimBackgroundWhisperInstall, extractImportUrl, importUrlKind, isVideoFile, shouldArmAutostart, shouldAutoStart, shouldBackgroundInstallWhisper, UNDO_MS } from './pasteStart'
import { readImportPreferences } from './importPreferencesStore'
import TranscriptionGatePrompt from './TranscriptionGatePrompt'
import { isRecoveryCode, probeConfig, type RecoveryController } from './transcriptionRecovery'
import { browserCookieRecovery, cookieAssistFromLocation, stageBrowserCookieRecovery, stagedRecoveryUrl } from './browserCookieRecovery'
import { SETTINGS_SAVED_EVENT } from './settingsReturn'
import { useTranscriptionRecovery } from './useTranscriptionRecovery'
import UrlPreview, { shouldSuggestFirstWindow, type UrlInspectPreview } from './UrlPreview'
import './studio.css'
import './quick-output.css'

function validationHint(check?: ReadinessCheck | null) {
  if (check?.code === 'model_validation_failed') return t('型号 {{model}} 未通过校验，请更换型号或重新测试。', { model: check.label || '' })
  if (check?.code === 'validation_failed') return t('模型连接未通过校验。请到「设置 → 服务商与模型」按提示改密钥或地址后再生成。')
  return ''
}

const parseImportUrl = (raw: string): string | null => {
  if (typeof extractImportUrl === 'function') return extractImportUrl(raw)
  return importUrlKind(raw) ? raw.trim() : null
}

function issueCopy(item: ReadinessIssue) {
  if (item.code === 'no_model') return t('服务商已保存，请选择精彩片段分析模型。')
  const hint = validationHint(item)
  if (hint) return hint
  if (item.key === 'analysis' && item.code === 'image_model_in_analysis') return t('{{model}} 是生图模型，只能用于封面，不能做分析。请到「设置 → 服务商与模型」改用对话模型后再生成。', { model: item.label || '' })
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
  if (item.code === 'no_model') return t('选择分析模型')
  if (item.repair === 'settings_ai') return (validationHint(item) || item.code === 'image_model_in_analysis') ? t('去设置修改') : t('连接 AI 服务')
  if (item.repair === 'install_whisper') return item.model ? t('下载转写模型') : t('安装 Whisper')
  if (item.repair === 'settings_transcription') return t('转写设置')
  if (item.repair === 'settings_vision') return t('视觉设置')
  return ''
}


function BrowserCookieControl({ browser, busy, onChange, assist, selectRef }: {
  browser: string
  busy: boolean
  onChange: (value: string) => void
  assist: boolean
  selectRef?: Ref<HTMLSelectElement>
}) {
  return <>
    <label className="studio-field" htmlFor={assist ? 'studio-browser-cookie' : undefined}>{t("使用浏览器登录状态")}
      <select id={assist ? 'studio-browser-cookie' : undefined} ref={selectRef} value={browser} onChange={event => onChange(event.target.value)} disabled={busy}>
        <option value="">{t("不使用")}</option>
        {['chrome', 'edge', 'safari', 'firefox'].map(name => <option key={name} value={name}>{name}</option>)}
      </select>
    </label>
    <p className="studio-muted">{assist ? t("还没有选择浏览器。选一个已登录的浏览器后再生成。这个浏览器如果正开着，请先完全退出，或换一个浏览器。") : t("仅在下载需要登录时选择，不会自动读取浏览器 Cookie。")}</p>
  </>
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
  if (reason === 'analysis' || reason === 'visual' || reason === 'transcription') {
    const hint = validationHint(readiness?.checks?.[reason])
    if (hint) return hint
  }
  if (reason === 'analysis') {
    const code = readiness?.checks?.analysis?.code
    if (code === 'no_model') return t('服务商已保存，请选择精彩片段分析模型。')
    if (code === 'image_model_in_analysis') {
      const model = readiness?.checks?.analysis?.label || ''
      return t('{{model}} 是生图模型，只能用于封面，不能做分析。请到「设置 → 服务商与模型」改用对话模型后再生成。', { model })
    }
    return t('请先连接 AI 服务，再导入视频。')
  }
  if (reason === 'transcription') return t('还没有可用的转写。可以附上 SRT 字幕，或先准备好转写。')
  if (reason === 'visual') return readiness?.checks?.visual?.code === 'vision_unsupported'
    ? t('画面理解使用的模型不能看图。请到「设置 → 服务商与模型」换一个能看图的模型后再生成。')
    : t('请先配好画面分析模型，再生成成片。')
  if (reason === 'ffmpeg') return t('找不到 FFmpeg，无法生成成片。')
  return ''
}

// A settings round trip stays in this window. File objects never enter browser storage or history.
type ImportDraft = {
  source: 'link' | 'file'
  url: string
  file: File | null
  subtitle: File | null
  options: ImportOptions
  platforms: string[]
  browser: string
  platformSource: PlatformSource
}
let settingsDraft: ImportDraft | null = null

export default function CreativeImport({ onImported, blocked = false, onBlocked, onExample, exampleBusy = false }: {
  onImported: () => Promise<void>
  blocked?: boolean
  onBlocked?: () => void
  onExample?: () => void
  exampleBusy?: boolean
}) {
  useTranslation()
  const navigate = useNavigate()
  const remembered = flagEnabled('remember_platforms')
  const reuse = useRef(takeReuseImport())
  const restored = useRef(reuse.current ? null : settingsDraft).current
  useEffect(() => { settingsDraft = null }, [])
  const initialPlatforms = useRef(
    reuse.current?.platforms?.length
      ? { platforms: reuse.current.platforms, source: 'user' as PlatformSource }
      : resolvePlatforms(remembered, uiLocale(), readRememberedPlatforms()),
  )
  const [source, setSource] = useState<'link' | 'file'>(restored?.source || 'link')
  const [url, setUrl] = useState(() => {
    if (restored) return restored.url
    const incoming = reuse.current?.sourceUrl || reuse.current?.sourceMeta?.source_url
    return typeof incoming === 'string' ? incoming : ''
  })
  const [file, setFile] = useState<File | null>(restored?.file || null)
  const replayFile = useRef<{ file: File; source: ReplayFileSource; replay?: ChannelReplay } | null>(null)
  const [remote, setRemote] = useState<RemoteReplay>()
  const activeRemote = source === 'file' && !file ? remote : undefined
  const replayOrigin = activeRemote ? (activeRemote.kind === 'obs' ? 'obs' : 'twitch') : source === 'file' && replayFile.current?.file === file ? replayFile.current?.source : undefined
  const [subtitle, setSubtitle] = useState<File | null>(restored?.subtitle || null)
  const videoInput = useRef<HTMLInputElement>(null)
  const subtitleInput = useRef<HTMLInputElement>(null)
  const [options, setOptions] = useState<ImportOptions>(restored?.options || {...defaultImportOptions})
  const templatesOn = useFlag('pkg_templates_v1') === true
  const visualOn = useFlag('pkg_template_picker_visual') === true
  const [browser, setBrowser] = useState(restored?.browser || '')
  const [cookieAssistLocal, setCookieAssistLocal] = useState(false)
  const assist = cookieAssistLocal || cookieAssistFromLocation(
    typeof window === 'undefined' ? '' : (window.location?.search || ''),
    typeof window === 'undefined' ? '' : (window.location?.hash || ''),
  )
  const browserRef = useRef<HTMLSelectElement | null>(null)
  useEffect(() => {
    if (!assist) return
    setSource('link')
    const incoming = stagedRecoveryUrl()
    if (incoming) { setUrl(incoming); setFile(null) }
    const node = browserRef.current
    if (!node) return
    try { node.focus() } catch { /* focus is optional */ }
    try { node.scrollIntoView({ block: 'center' }) } catch { /* not a browser */ }
  }, [assist])
  const [platforms, setPlatforms] = useState<string[]>(restored?.platforms || initialPlatforms.current.platforms)
  const [preferences, setPreferences] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [readiness, setReadiness] = useState<ImportReadiness | null>(null)
  const currentReadiness = readiness
  const [settled, setSettled] = useState(false)
  const [platformOpen, setPlatformOpen] = useState(!!reuse.current?.platforms?.length)
  const [pending, setPending] = useState<{ trigger: 'paste' | 'drop' } | null>(null)
  const [urlPreview, setUrlPreview] = useState<UrlInspectPreview | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const previewTicket = useRef(0)
  const previewUrlRef = useRef('')

  const [dragging, setDragging] = useState(false)
  const [longGate, setLongGate] = useState<{ open: boolean; durationSec: number | null; trigger: 'paste' | 'drop' | 'button' }>({ open: false, durationSec: null, trigger: 'button' })
  const [firstWindowGate, setFirstWindowGate] = useState<{ open: boolean; trigger: 'paste' | 'drop' | 'button' }>({ open: false, trigger: 'button' })
  const firstWindowDecided = useRef(false)
  /** Synchronous override so FormData sees the choice before setState flushes (T2). */
  const sourceWindowOverride = useRef<ImportOptions['source_window'] | undefined>(undefined)
  useEffect(() => {
    if (activeRemote) {
      if (activeRemote.kind === 'obs') {
        setLongGate(prev => ({ ...prev, durationSec: Math.round(activeRemote.seconds) || null })); return
      }
      const parts = /^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/.exec(activeRemote.duration ?? '')
      const seconds = parts ? Number(parts[1] || 0) * 3600 + Number(parts[2] || 0) * 60 + Number(parts[3] || 0) : 0
      setLongGate(prev => ({ ...prev, durationSec: seconds || null })); return
    }
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
  }, [file, source, activeRemote])
  const platformSource = useRef<PlatformSource>(restored?.platformSource || initialPlatforms.current.source)
  const overridden = useRef(false)
  const starting = useRef(false)
  const recoverRef = useRef<RecoveryController>(null as unknown as RecoveryController)
  const submitRef = useRef<(trigger: 'paste' | 'drop' | 'button', fresh?: ImportReadiness | null, confirmed?: boolean) => Promise<void>>(async () => {})
  const allowLink = flagEnabled('link_import_without_whisper')
  const dropZone = flagEnabled('import_drop_zone')
  const hidePreferences = flagEnabled('hide_legacy_entrypoints')
  const pasteFlag = String(flagValue('one_click_paste_start'))
  const platformSubtitles = source === 'link' && previewUrlRef.current === url.trim() && urlPreview?.preview_route === 'platform_subtitle'
  const blockOptions = { source, allowLinkWithoutWhisper: allowLink || platformSubtitles }
  const transcriber = readiness?.checks?.transcription
  const needsSourceTranscript = !subtitle && !platformSubtitles &&
    (source === 'file' ? !!file : urlPreview?.preview_route === 'local_transcription') &&
    transcriber?.ok === false && !transcriber.skippable
  const subtitleLabel = subtitle?.name || (platformSubtitles ? t('平台字幕') : '')
  const latestDraft = useRef<ImportDraft | null>(null)
  latestDraft.current = { source, url, file, subtitle, options, platforms, browser, platformSource: platformSource.current }
  useEffect(() => () => {
    // The header Settings button can also interrupt an unfinished import.
    if (window.location?.hash?.split('?')[0] === '#/settings') settingsDraft = latestDraft.current
  }, [])
  const openSettings = (destination: string) => {
    settingsDraft = latestDraft.current
    navigate(destination + (destination.includes('?') ? '&' : '?') + 'return_import=1')
  }
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
    if (!hidePreferences || restored) return
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
  const analysisBlocked = analysisNeedsSetup(readiness)
  useEffect(() => {
    if (pasteFlag !== 'autostart' && !dropZone) return
    const onPaste = (event: ClipboardEvent) => {
      const target = event.target
      if (target instanceof HTMLElement && target.closest('.ac-import-setup')) return
      if (target instanceof HTMLElement && target.closest('input, textarea, [contenteditable="true"]') && !target.closest('.ac-creative-import')) return
      const text = event.clipboardData?.getData('text') || ''
      const extracted = parseImportUrl(text)
      if (!extracted || !shouldAutoStart(pasteFlag, 'paste')) return
      event.preventDefault()
      arm('paste', { url: extracted })
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [pasteFlag, dropZone, busy, settled, allowLink, source, analysisBlocked])
  const issues = visibleIssues(readiness, !!subtitle, blockOptions)
  const repair = async (item: ReadinessIssue) => {
    // #353: the readiness list's install button goes through the one recovery controller (no second install flow).
    if (item.repair === 'install_whisper') {
      resumeSubmit.current = false
      setError('')
      recover.open(item.code, item.model)
      await recover.install()
      return
    }
    if (item.repair === 'settings_ai' && blocked) { onBlocked?.(); return }
    const destination = item.code === 'no_model' ? '/settings?section=analysis' : repairDestination(item.repair)
    if (destination) openSettings(destination)
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
  const readyToStart = (trigger: 'paste' | 'drop' | 'button', next?: { url?: string; file?: File | null }, readiness: ImportReadiness | null = currentReadiness, preview = urlPreview) => {
    if (blocked) { trackExperience('import_blocked', { reason: 'setup_required', placement: 'home_setup' }); setError(t("请先连接 AI 服务，再导入视频。")); onBlocked?.(); return false }
    const nextFile = next && 'file' in next ? next.file : file
    const nextUrl = next?.url ?? url
    const nextSource = next?.file ? 'file' : next?.url ? 'link' : source
    if (nextSource === 'file' ? !nextFile && !activeRemote : !nextUrl.trim()) { setError(t("请先添加视频文件或链接")); return false }
    const reason = submissionBlock(readiness, !!subtitle, settled, { source: nextSource, allowLinkWithoutWhisper: allowLink || (previewUrlRef.current === nextUrl.trim() && preview?.preview_route === 'platform_subtitle') })
    if (reason === 'pending') { setError(blockMessage(reason, readiness)); return false }
    trackAsrReadiness(asrReadinessProperties(readiness, !!subtitle))
    const check = readiness?.checks?.transcription
    if (reason === 'transcription' && !subtitle && !check?.skippable && isRecoveryCode(check?.code)) {
      setError(''); resumeSubmit.current = true; recover.open(check!.code, check!.model); return false
    }
    if (reason) { setError(blockMessage(reason, readiness)); return false }
    if (trigger !== 'button') setError('')
    return true
  }
  const clearPreview = () => {
    previewTicket.current += 1
    previewUrlRef.current = ''
    setUrlPreview(null)
    setPreviewLoading(false)
  }
  const inspectInFlight = useRef<{ url: string; ticket: number; promise: Promise<UrlInspectPreview | null> } | null>(null)
  const inspectTimedOut = useRef(false)
  const previewBrowserRef = useRef('')
  const inspect = async (nextUrl: string, _trigger: 'paste' | 'drop' | 'blur' = 'paste') => {
    const trimmed = parseImportUrl(nextUrl) || nextUrl.trim()
    if (!importUrlKind(trimmed)) { clearPreview(); return null }
    if (previewUrlRef.current === trimmed && previewBrowserRef.current === (browser || '') && urlPreview) return urlPreview
    const ticket = ++previewTicket.current
    previewUrlRef.current = trimmed
    previewBrowserRef.current = browser || ''
    inspectTimedOut.current = false
    setPreviewLoading(true)
    setPending(null)
    try {
      const result = await studioApi.inspectUrl({
        url: trimmed,
        ...(browser ? { browser } : {}),
      })
      if (ticket !== previewTicket.current) return null
      const preview = result as UrlInspectPreview
      setUrlPreview(preview)
      setLongGate(prev => ({ ...prev, durationSec: typeof preview.duration === 'number' ? preview.duration : null }))
      trackImportPreviewShown({
        route: preview.preview_route,
        duration_bucket: durationBucket(preview.duration),
        has_platform_subtitle: !!preview.has_manual_subtitle,
      })
      return preview
    } catch (e) {
      if (ticket !== previewTicket.current) return null
      setUrlPreview(null)
      const errObj = e as { code?: string; response?: { status?: number } } | null
      const status = errObj?.response?.status
      inspectTimedOut.current = status === 504 || errObj?.code === 'ECONNABORTED' || errObj?.code === 'ETIMEDOUT'
      const code = errorCode(e)
      const message = t(errorText(e))
      if (browserCookieRecovery(code, errorText(e))) {
        stageBrowserCookieRecovery(trimmed)
        setCookieAssistLocal(true)
      }
      setError(message)
      return null
    } finally {
      if (ticket === previewTicket.current) setPreviewLoading(false)
    }
  }
  const runInspect = (nextUrl: string, trigger: 'paste' | 'drop' | 'blur') => {
    const url = nextUrl.trim()
    const pending = inspectInFlight.current
    if (pending?.url === url && pending.ticket === previewTicket.current) return pending.promise
    const promise = inspect(url, trigger)
    inspectInFlight.current = { url, ticket: previewTicket.current, promise }
    void promise.finally(() => { if (inspectInFlight.current?.promise === promise) inspectInFlight.current = null })
    return promise
  }
  const needsPreviewTranscriptionInstall = !!(
    urlPreview?.preview_route === 'local_transcription'
    && readiness?.checks?.transcription?.ok === false
    && !subtitle
    && !readiness?.checks?.transcription?.skippable
    && isRecoveryCode(readiness?.checks?.transcription?.code)
  )
  const arm = (trigger: 'paste' | 'drop', next: { url?: string; file?: File }) => {
    // drop, global paste and the file picker all come through here; while a submit is running
    // (including its readiness re-check) the source is locked, so what is shown is what gets uploaded.
    if (starting.current) return
    setRemote(undefined)
    if (next.file) {
      setFile(next.file); setUrl(''); setSource('file'); clearPreview()
      if (analysisBlocked) return
      if (!shouldAutoStart(pasteFlag, trigger)) return
      if (!readyToStart(trigger, next)) return
      setPending({ trigger })
      return
    }
    if (next.url) { setUrl(next.url); setFile(null); setSource('link') }
    // The setup card owns the zone. Keep the material, but do not start or reopen the overlay.
    if (analysisBlocked) return
    // F4: inspect first; autostart countdown begins only after the preview card is ready.
    void (async () => {
      const preview = await runInspect(next.url || '', trigger)
      if (!preview) return
      if (!shouldArmAutostart(pasteFlag, trigger, true)) return
      const needsInstall = preview.preview_route === 'local_transcription'
        && readiness?.checks?.transcription?.ok === false
        && !subtitle
        && !readiness?.checks?.transcription?.skippable
        && isRecoveryCode(readiness?.checks?.transcription?.code)
      if (needsInstall) return
      if (!readyToStart(trigger, next, readiness, preview)) return
      setPending({ trigger })
    })()
  }
  const undo = () => {
    const trigger = pending?.trigger
    setPending(null)
    if (trigger) trackOneClickUndone({ trigger }, flagAssigned('one_click_paste_start'))
  }
  const submit = async (trigger: 'paste' | 'drop' | 'button' = 'button', fresh?: ImportReadiness | null, confirmed = false) => {
    if (starting.current) return
    if (trigger === 'button') setPending(null)
    let preview = urlPreview
    const normalizedUrl = source === 'link' ? (parseImportUrl(url) || url.trim()) : ''
    if (source === 'link' && normalizedUrl && normalizedUrl !== url) setUrl(normalizedUrl)
    if (source === 'link' && normalizedUrl && !preview) {
      preview = await runInspect(normalizedUrl, 'blur')
      if (starting.current) return
      if (!preview && !inspectTimedOut.current) return
      if (preview?.preview_route === 'local_transcription'
        && readiness?.checks?.transcription?.ok === false
        && !subtitle
        && !readiness?.checks?.transcription?.skippable
        && isRecoveryCode(readiness?.checks?.transcription?.code)) {
        const check = readiness?.checks?.transcription
        resumeSubmit.current = true
        recover.open(check!.code, check!.model)
        return
      }
    }
    if (platforms.includes('youtube_long') && !confirmed) {
      if (!readyToStart(trigger, undefined, fresh ?? readiness, preview)) return
      setLongGate(prev => ({ ...prev, open: true, trigger }))
      return
    }
    // T2: file import (or link without UrlPreview dual buttons) — ask before spending ASR on a long first source.
    const durationForWindow = source === 'link'
      ? (typeof preview?.duration === 'number' ? preview.duration : null)
      : longGate.durationSec
    if (
      !confirmed
      && !firstWindowDecided.current
      && shouldSuggestFirstWindow(hasSuccessHistory(), durationForWindow)
    ) {
      if (!readyToStart(trigger, undefined, fresh ?? readiness, preview)) return
      setFirstWindowGate({ open: true, trigger })
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
      if (!readyToStart(trigger, undefined, report, preview)) return
      setError('')
      const flowId = telemetryId()
      const body = new FormData()
      if (activeRemote?.kind === 'obs') {
        body.append('obs_capture_id', activeRemote.id)
        body.append('replay_source', 'obs')
      } else if (activeRemote && 'direct_video_id' in activeRemote && activeRemote.direct_video_id) {
        body.append('twitch_video_id', activeRemote.direct_video_id)
        body.append('channel_replay_id', activeRemote.id)
        body.append('replay_source', 'twitch_file')
      } else {
        if (replayOrigin && replayFile.current?.replay) body.append('channel_replay_id', replayFile.current.replay.id)
        if (replayOrigin) body.append('replay_source', replayOrigin + '_file')
      }
      body.append('goal', replayOrigin ? 'auto' : options.goal); body.append('language', options.language); body.append('instruction', options.instruction)
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
      const windowChoice = sourceWindowOverride.current !== undefined ? sourceWindowOverride.current : options.source_window
      if (windowChoice && typeof windowChoice.end === 'number') {
        body.append('source_window_start', String(windowChoice.start ?? 0))
        body.append('source_window_end', String(windowChoice.end))
      }
      if (subtitle) body.append('subtitle', subtitle)
      body.append('name', activeRemote ? activeRemote.title : file && source === 'file' ? file.name.replace(/\.[^.]+$/, '') : t("智能剪辑"))
      if (source === 'file' && file) body.append('video', file)
      else if (!activeRemote) { body.append('url', normalizedUrl || url.trim()); if (browser) body.append('browser', browser) }
      body.append('flow_id', flowId)
      const skippedWhisper = allowLink && source !== 'file' && !!readiness && !readiness?.checks?.transcription?.ok && !subtitle
      const result = await studioApi.import(body)
      trackOneClickStarted({
        trigger, flow_id: flowId, platform_count: platforms.length, platform_source: platformSource.current,
        has_subtitle: !!subtitle, transcription_route: transcriptionRoute({
          hasSubtitle: !!subtitle,
          code: readiness?.checks?.transcription?.code,
          skippedWhisper,
          previewRoute: source === 'link' ? preview?.preview_route : undefined,
        }),
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
      else if (activeRemote?.kind === 'obs' && errorText(e) === 'replay_unavailable') setError(t('replays.requestError'))
      else if (activeRemote?.kind === 'twitch' && errorText(e) === 'channel_reconnect') setError(t('channels.reconnect'))
      else if (activeRemote?.kind === 'twitch' && ['channel_provider', 'channel_network', 'archive_unavailable', 'replay_download_failed', 'replay_download_busy', 'channel_mismatch'].includes(errorText(e))) setError(t('channels.directFailed'))
      else setError(t(errorText(e)))  // includes coded source refusals (source_unreadable ...): shown at once
    } finally { starting.current = false; setBusy(false) }
  }
  const attachSubtitle = (picked?: File) => {
    if (!picked) return
    if (!picked.name.toLowerCase().endsWith('.srt') || !picked.size || picked.size > 2 * 1024 * 1024) {
      setError(t('请选择 2 MB 以内的非空 SRT 字幕文件。'))
      return
    }
    resumeSubmit.current = false
    recover.close()
    setError('')
    setPending(null)
    setSubtitle(picked)
  }
  submitRef.current = submit
  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragging(false)
    const dropped = [...event.dataTransfer.files].find(item => isVideoFile(item))
    if (dropped) { arm('drop', { file: dropped }); return }
    const text = event.dataTransfer.getData('text/uri-list') || event.dataTransfer.getData('text/plain')
    const extracted = parseImportUrl(text)
    if (extracted) arm('paste', { url: extracted })
  }
  const names = platforms.map(platformLabel).join(uiLocale().toLowerCase().startsWith('zh') ? '、' : ', ')
  const youtubeLongOnlyTooShort = longGate.durationSec != null && longGate.durationSec < YOUTUBE_LONG_MIN_SEC && platforms.length > 0 && platforms.every(platform => platform === 'youtube_long')
  const replayPicker = <LiveReplayPicker disabled={busy} onOpen={() => { setPending(null); previewTicket.current++; setPreviewLoading(false) }} onRemote={replay => {
    if (starting.current) return
    setPending(null); clearPreview(); setFile(null); setUrl(''); setSubtitle(null); setSource('file')
    replayFile.current = null; setRemote(replay); setError('')
    sourceWindowOverride.current = undefined; firstWindowDecided.current = false
  }} onFile={(picked, origin, replay) => {
    if (starting.current) return
    setPending(null); clearPreview(); setSource('file'); setFile(picked); setUrl(''); setSubtitle(null)
    setRemote(undefined); replayFile.current = { file: picked, source: origin, replay }
    setError(''); setLongGate({ open: false, durationSec: null, trigger: 'button' })
    sourceWindowOverride.current = undefined; firstWindowDecided.current = false
  }} />
  if (blocked) return <section className="ac-welcome" aria-labelledby="welcome-title">
    <div className="ac-welcome-copy">
      <h1 id="welcome-title">{t('把长视频剪成精彩片段')}</h1>
      <p>{t('导入一段视频或粘贴链接，让 AI 帮你找到值得分享的片段。')}</p>
      <Btn variant="cta" onClick={onBlocked}>{t('剪自己的视频')}</Btn>
    </div>
    <figure className="ac-welcome-sample" aria-labelledby="welcome-sample-title">
      <figcaption>
        <span>{t('示例项目')}</span>
        <strong id="welcome-sample-title">{t('Sam Altman 访谈')}</strong>
        <button type="button" className="ac-welcome-play" disabled={exampleBusy} aria-busy={exampleBusy} onClick={onExample}>
          {exampleBusy ? t('加载中…') : t('先看示例')}
        </button>
      </figcaption>
    </figure>
  </section>
  if (analysisBlocked) {
    return <section className="ac-creative-import">
      <div className="studio-import-box">
        {replayPicker}
        <ImportSetupCard onExample={onExample} exampleBusy={exampleBusy} keptMaterial={Boolean(url.trim() || file || activeRemote)} />
      </div>
    </section>
  }
  return <section className="ac-creative-import">
    <h1 className="ac-title">{t("放入视频，直接生成可发布成片。")}</h1>
    <p className="studio-muted">{t("选择发布平台，AI 会自动挑选内容、完成剪辑与渲染。生成后可直接下载或继续编辑。")}</p>
    <div className="studio-import-box">
      {activeRemote ? <div className="studio-field"><strong>{activeRemote.title}</strong><div>{activeRemote.kind === 'obs' ? 'OBS Studio' : 'Twitch'} <button type="button" className="studio-link" disabled={busy} onClick={() => setRemote(undefined)}>{t('移除')}</button></div></div> : dropZone ? <div className={`ac-dropzone${dragging ? ' is-hot' : ''}`} onDragEnter={event => { event.preventDefault(); setDragging(true) }} onDragOver={event => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
        <p className="ac-dropzone-title">{t('把链接或视频放在这里')}</p>
        <p className="ac-dropzone-hint">{t('粘贴链接，或拖入一个视频文件。')}</p>
        <label className="studio-field ac-dropzone-field"><span className="studio-sr">{t("视频链接")}</span><textarea placeholder={t("粘贴 B 站或 YouTube 视频链接")} value={url} onChange={event => { setPending(null); clearPreview(); setUrl(event.target.value); if (event.target.value) { setFile(null); setSource('link') } }} onBlur={event => { const value = event.target.value.trim(); if (importUrlKind(value)) void runInspect(value, 'blur') }} disabled={busy}/></label>
        {file && <p className="ac-dropzone-file"><span>{file.name}</span><button type="button" className="studio-link" disabled={busy} onClick={() => setFile(null)}>{t('移除')}</button></p>}
        <label className="studio-link ac-dropzone-file-label">{t('选择一个视频文件')}<input type="file" aria-label={t("视频文件")} accept="video/mp4,video/webm,video/quicktime,.mkv,.avi" disabled={busy} onChange={event => { const picked = event.target.files?.[0] || null; if (picked) arm('drop', { file: picked }) }}/></label>
      </div> : <>
        <div className="studio-row"><Segmented ariaLabel={t("导入来源")} value={source} onChange={v => { if (!busy && v !== source) { setRemote(undefined); clearPreview(); setPending(null); setSource(v) } }} options={[{value:'link',label:t("链接导入")},{value:'file',label:t("文件导入")}]}/></div>
        {source==='link'?<label className="studio-field"><span className="studio-sr">{t("视频链接")}</span><textarea placeholder={t("粘贴 B 站或 YouTube 视频链接")} value={url} onChange={e=>{ setPending(null); clearPreview(); setUrl(e.target.value) }} onBlur={e => { const value = e.target.value.trim(); if (importUrlKind(value)) void runInspect(value, 'blur') }} onPaste={event => { const text = event.clipboardData.getData('text'); if (importUrlKind(text) && shouldAutoStart(pasteFlag, 'paste')) { event.preventDefault(); arm('paste', { url: text.trim() }) } }} disabled={busy}/></label> : (
          <div className="studio-file">
            <input type="file" hidden ref={videoInput} aria-label={t('视频文件')}
              accept="video/mp4,video/webm,video/quicktime,.mkv,.avi" disabled={busy}
              onChange={event => {
                const picked = event.currentTarget.files?.[0]
                event.currentTarget.value = ''
                if (picked) arm('drop', { file: picked })
              }} />
            {file && <span className="studio-file-name" title={file.name} role="status">{file.name}</span>}
            <Btn size="sm" disabled={busy} aria-describedby="studio-video-formats" onClick={() => videoInput.current?.click()}>
              {file ? t('换一个视频') : t('选择一段视频')}
            </Btn>
            <small id="studio-video-formats">MP4 / MOV / MKV / WEBM / AVI</small>
          </div>
        )}
      </>}
      <div className="studio-source-subtitles">
        <input type="file" accept=".srt" hidden ref={subtitleInput} aria-label={t('已有字幕')} disabled={busy}
          onChange={event => { attachSubtitle(event.target.files?.[0]); event.target.value = '' }} />
        {needsSourceTranscript && recovery.phase === 'idle' && <span>{t('选择字幕来源')}</span>}
        {subtitleLabel && <span role="status">{t('将使用 {{name}}', { name: subtitleLabel })}</span>}
        <Btn size="sm" disabled={busy} onClick={() => subtitleInput.current?.click()}>{t(subtitle ? '更换字幕' : '上传 SRT 字幕')}</Btn>
        {needsSourceTranscript && recovery.phase === 'idle' && <>
          {transcriber?.repair === 'install_whisper' && <Btn size="sm" disabled={busy}
            onClick={() => { resumeSubmit.current = false; recover.open(transcriber.code, transcriber.model) }}>{t('本机转写')}</Btn>}
          <Btn size="sm" disabled={busy} onClick={() => openSettings(CLOUD_TRANSCRIPTION_DESTINATION)}>{t('改用云端转写')}</Btn>
        </>}
        {subtitle && <Btn size="sm" variant="text" disabled={busy} onClick={() => setSubtitle(null)}>{t('移除')}</Btn>}
      </div>
      {templatesOn && visualOn && platforms.some(platform => !['bilibili', 'youtube_long', 'original'].includes(platform)) && <StyleProbeLine sourceKey={source === 'file' ? (file ? `file:${file.name}:${file.size}:${file.lastModified}` : null) : (url.trim() ? `url:${url.trim()}` : null)} />}
      {replayPicker}
      {replayOrigin && replayFile.current?.replay && <p>{replayFile.current.replay.title}</p>}
      {remembered ? <div className="ac-platform-line"><p>{t('为 {{names}} 制作', { names })}</p><button type="button" className="studio-link" disabled={busy} onClick={() => setPlatformOpen(open => !open)}>{t('改')}</button></div> : null}
      {(!remembered || platformOpen) && <PlatformPicker value={platforms} onChange={changePlatforms} disabled={busy}/>}
      {templatesOn && platforms.some(platform => !['bilibili', 'youtube_long', 'original'].includes(platform)) && <TemplatePicker visual={visualOn} disabled={busy} value={options.html_template} sourceKey={source === 'file' ? (file ? `file:${file.name}:${file.size}:${file.lastModified}` : null) : (url.trim() ? `url:${url.trim()}` : null)} url={url} file={file} sourceKind={source === 'file' ? (file ? 'file' : 'none') : (url.trim() ? 'link' : 'none')} onChange={(html_template: HtmlTemplateChoice) => setOptions({...options, html_template})}/>}
      {!templatesOn && platforms.some(platform => !['bilibili', 'youtube_long', 'original'].includes(platform)) && <div className="studio-field"><span>{t('竖版版式')}</span><Select aria-label={t('竖版版式')} disabled={busy} value={options.portrait_style || 'auto'} options={[{value:'auto',label:t('按平台默认')},{value:'interview',label:t('访谈式（人物窗口）')},{value:'podcast',label:t('播客式（满屏）')}]} onChange={portrait_style=>setOptions({...options,portrait_style})}/><small>{t('仅调整竖版布局，字幕与发布文案语言仍按平台。')}</small></div>}
      {templatesOn && options.html_template === 'classic' && platforms.some(platform => !['bilibili', 'youtube_long', 'original'].includes(platform)) && <div className="studio-field"><span>{t('竖版版式')}</span><Select aria-label={t('竖版版式')} disabled={busy} value={options.portrait_style || 'auto'} options={[{value:'auto',label:t('按平台默认')},{value:'interview',label:t('访谈式（人物窗口）')},{value:'podcast',label:t('播客式（满屏）')}]} onChange={portrait_style=>setOptions({...options,portrait_style})}/><small>{t('仅调整竖版布局，字幕与发布文案语言仍按平台。')}</small></div>}
      <OutputCaptionsSwitch label={t('成片显示字幕')} hint={t('关闭后成片不带字幕。标题只在封面上，不会烧进视频。')} />
      <details className="studio-details"><summary>{t("有特别要求？（选填）")}</summary><label className="studio-field"><span className="studio-sr">{t("制作要求")}</span><input aria-label={t("制作要求")} placeholder={t("例如：保留完整观点或挑战过程")} maxLength={1000} value={options.instruction} disabled={busy} onChange={e=>setOptions({...options,instruction:e.target.value})}/></label></details>
      {issues.length > 0 && <div className="studio-readiness" role="status">
        {issues.map(item => <div className="studio-readiness-row" key={item.key}>
          <StatusDot tone={item.code === 'whisper_installing' || item.code === 'whisper_model_downloading' ? 'accent' : 'muted'} label={issueCopy(item)} />
          {item.repair !== 'none' && <Btn size="sm" disabled={busy || repairing} loading={repairing && item.repair === 'install_whisper'} onClick={() => void repair(item)}>{repairLabel(item)}</Btn>}
        </div>)}
      </div>}
      {(source === 'link' && (previewLoading || urlPreview)) && <UrlPreview
        preview={urlPreview}
        loading={previewLoading}
        needsTranscriptionInstall={needsPreviewTranscriptionInstall}
        installing={repairing}
        suggestFirstWindow={shouldSuggestFirstWindow(hasSuccessHistory(), urlPreview?.duration ?? null)}
        onInstallTranscription={() => {
          const check = readiness?.checks?.transcription
          resumeSubmit.current = false
          setError('')
          recover.open(check?.code || 'whisper_not_installed', check?.model)
          void recover.install()
        }}
        onConfirm={() => { setPending(null); void submit('button') }}
        onConfirmFirstWindow={() => {
          firstWindowDecided.current = true
          sourceWindowOverride.current = { start: 0, end: FIRST_WINDOW_END_SEC }
          setOptions(prev => ({ ...prev, source_window: { start: 0, end: FIRST_WINDOW_END_SEC } }))
          setPending(null)
          void submit('button', undefined, true)
        }}
        onConfirmFull={() => {
          firstWindowDecided.current = true
          sourceWindowOverride.current = null
          setOptions(prev => ({ ...prev, source_window: null }))
          setPending(null)
          void submit('button', undefined, true)
        }}
        onDismiss={() => { clearPreview(); setUrl(''); setPending(null); firstWindowDecided.current = false }}
      />}
      {platforms.includes('youtube_long') && <p className="studio-muted" role="note">{longFormNotice(longGate.durationSec, platforms)}</p>}
      {assist && <details className="studio-details" open><summary>{t("下载遇到登录限制时")}</summary><BrowserCookieControl assist browser={browser} busy={busy} onChange={setBrowser} selectRef={browserRef} /></details>}
      {pending && <div className="ac-undo" role="status"><span>{t('即将开始制作。')}</span><button type="button" className="ac-undo-action" onClick={undo}>{t('撤销')}</button></div>}
      <div className="studio-row studio-import-bottom"><div><span className="studio-muted">{t('会按所选平台自动制作，数量由素材内容决定。')}</span>{!hidePreferences && <button className="studio-link studio-preferences-link" disabled={busy} onClick={()=>setPreferences(true)}>{t("高级偏好")}</button>}</div><Btn variant="cta" disabled={!settled} loading={busy} onClick={() => submit('button')}>{!settled ? t('正在确认导入条件…') : busy && activeRemote ? t('channels.directWorking') : busy ? t("正在生成") : replayOrigin ? t("replays.generate") : t("生成成片")}</Btn></div>
      <TranscriptionGatePrompt state={recovery} busy={busy} onInstall={() => recover.install()} onRetry={() => recover.retry()} onContinue={() => continueAfterRecovery(null)} navigate={openSettings} onAttach={() => subtitleInput.current?.click()}/>
      {error&&<p className="studio-error" role="alert">{error}</p>}
    </div>
    <Dialog open={preferences} onClose={()=>setPreferences(false)} title={t("制作偏好")} description={t("默认由 AI 匹配。你指定的选项优先，生成后也可以修改。")} footer={<div className="studio-actions"><Btn onClick={()=>{setOptions({...defaultImportOptions,instruction:options.instruction});setSubtitle(null);setBrowser('')}}>{t("恢复自动")}</Btn><Btn variant="cta" onClick={()=>setPreferences(false)}>{t("完成")}</Btn></div>}>
      <ImportPreferences value={options} onChange={setOptions}/>
      {source==='link'&&<details className="studio-details"><summary>{t("下载遇到登录限制时")}</summary><BrowserCookieControl browser={browser} busy={busy} onChange={setBrowser} assist={false} /></details>}
    </Dialog>
    <Dialog open={longGate.open} onClose={() => setLongGate(prev => ({ ...prev, open: false }))} title={t('YouTube 横屏')} description={youtubeLongOnlyTooShort ? <>{longFormNotice(longGate.durationSec, platforms)} {t('请再选一个其他平台。')}</> : longFormNotice(longGate.durationSec, platforms)} footer={youtubeLongOnlyTooShort ? <div className="studio-actions"><Btn onClick={() => setLongGate(prev => ({ ...prev, open: false }))}>{t('知道了')}</Btn></div> : <div className="studio-actions"><Btn onClick={() => setLongGate(prev => ({ ...prev, open: false }))}>{t('取消')}</Btn><Btn variant="cta" onClick={() => { const trigger = longGate.trigger || 'button'; setLongGate(prev => ({ ...prev, open: false })); void submit(trigger, undefined, true) }}>{t('确认并开始')}</Btn></div>} />
    <Dialog open={firstWindowGate.open} onClose={() => setFirstWindowGate(prev => ({ ...prev, open: false }))} title={t('首次素材建议')} description={t('第一次建议先试 30 分钟以内，确认模型配置没问题')} footer={<div className="studio-actions" data-testid="t2-first-window-dialog"><Btn onClick={() => setFirstWindowGate(prev => ({ ...prev, open: false }))}>{t('取消')}</Btn><Btn onClick={() => { firstWindowDecided.current = true; sourceWindowOverride.current = null; setOptions(prev => ({ ...prev, source_window: null })); setFirstWindowGate(prev => ({ ...prev, open: false })); void submit(firstWindowGate.trigger || 'button', undefined, true) }}>{t('处理全片')}</Btn><Btn variant="cta" onClick={() => { firstWindowDecided.current = true; sourceWindowOverride.current = { start: 0, end: FIRST_WINDOW_END_SEC }; setOptions(prev => ({ ...prev, source_window: { start: 0, end: FIRST_WINDOW_END_SEC } })); setFirstWindowGate(prev => ({ ...prev, open: false })); void submit(firstWindowGate.trigger || 'button', undefined, true) }}>{t('只处理前 30 分钟')}</Btn></div>} />
  </section>
}
