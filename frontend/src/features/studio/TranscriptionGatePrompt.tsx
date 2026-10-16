import { useEffect, useRef, useState } from 'react'
import { t } from '../../i18n'
import { Btn } from '../../ui'
import { CLOUD_TRANSCRIPTION_DESTINATION, repairDestination, type ReadinessCheck, type ReadinessIssue, type WaitProgress } from './importReadiness'

/** Sentinels in CreativeImport's error slot: render this prompt instead of plain error text. */
export const LOCAL_TRANSCRIPTION_GATE = '需要先安装本地转写'
export const LOCAL_TRANSCRIPTION_INSTALLING = '等待安装完成'

export interface TranscriptionGatePromptProps {
  kind: typeof LOCAL_TRANSCRIPTION_GATE | typeof LOCAL_TRANSCRIPTION_INSTALLING
  check?: ReadinessCheck | null
  busy: boolean
  repairing: boolean
  /** Existing Settings → Transcription install flow. */
  repair: (item: ReadinessIssue) => void | Promise<void>
  navigate: (to: string) => void
  /** R24 #232: one poll of the install / model download (readiness + progress). Without it the prompt only waits. */
  wait?: () => Promise<WaitProgress>
  /** Ready: start the same import again (one click). */
  onContinue?: () => void
  /** Failed or stalled: start the install / model download again. */
  retry?: () => void | Promise<void>
  pollMs?: number
  /** No progress for this long counts as a timeout (retry or settings). */
  stallMs?: number
}

const STALL_MS = 10 * 60 * 1000

/** R24 #232: waiting for Whisper (install or model download) never traps the user: progress while it runs,
 * one-click continue once ready, retry or transcription settings when it fails or stalls. */
function WaitingPrompt({ wait, onContinue, retry, navigate, busy, check, pollMs = 2000, stallMs = STALL_MS }: TranscriptionGatePromptProps) {
  const [state, setState] = useState<WaitProgress>({ state: 'waiting', phase: check?.code === 'whisper_model_downloading' ? 'download' : 'install' })
  const [stalled, setStalled] = useState(false)
  const [round, setRound] = useState(0)
  const last = useRef<{ percent: number | null | undefined; at: number }>({ percent: undefined, at: Date.now() })
  useEffect(() => {
    if (!wait) return
    let alive = true
    let timer: ReturnType<typeof setTimeout> | undefined
    last.current = { percent: undefined, at: Date.now() }
    const tick = async () => {
      let next: WaitProgress
      try { next = await wait() } catch { next = { state: 'waiting' } }
      if (!alive) return
      const now = Date.now()
      if (next.percent !== last.current.percent) last.current = { percent: next.percent, at: now }
      setState(next)
      if (next.state !== 'waiting') return
      if (now - last.current.at >= stallMs) { setStalled(true); return }
      timer = setTimeout(tick, pollMs)
    }
    void tick()
    return () => { alive = false; if (timer) clearTimeout(timer) }
  }, [wait, round, pollMs, stallMs])
  const again = async () => { setStalled(false); setState({ state: 'waiting', phase: state.phase }); await retry?.(); setRound(value => value + 1) }
  const failed = state.state === 'failed' || stalled
  const percent = typeof state.percent === 'number' ? Math.max(0, Math.min(100, Math.round(state.percent))) : null
  return <div className="studio-readiness" role="alertdialog" aria-label={t('等待安装完成')}>
    <b>{t('等待安装完成')}</b>
    {state.state === 'ready' ? <>
      <span>{t('本地转写已就绪，可以继续导入。')}</span>
      <div className="studio-actions"><Btn size="sm" disabled={busy} onClick={() => onContinue?.()}>{t('继续导入')}</Btn></div>
    </> : failed ? <>
      <span className="studio-error">{t(stalled ? '安装长时间没有进展，可以重试，或到转写设置里查看。' : '安装或模型下载失败，可以重试，或到转写设置里查看。')}</span>
      <div className="studio-actions">
        <Btn size="sm" disabled={busy} onClick={() => void again()}>{t('重试')}</Btn>
        <Btn size="sm" disabled={busy} onClick={() => navigate(repairDestination('settings_transcription') as string)}>{t('打开转写设置')}</Btn>
      </div>
    </> : <>
      <span>{t(state.phase === 'download' ? '正在下载转写模型，下载完成后即可继续。' : '本地 Whisper 正在安装，装好后再开始。')}</span>
      {percent != null && <span className="studio-muted" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>{t('已完成 {{percent}}%', { percent })}</span>}
    </>}
  </div>
}

/** 1.5.8 blocking prompt: install local Whisper, or open transcription settings. Never switches provider itself. */
export default function TranscriptionGatePrompt(props: TranscriptionGatePromptProps) {
  const { kind, check, busy, repairing, repair, navigate } = props
  if (kind === LOCAL_TRANSCRIPTION_INSTALLING) return <WaitingPrompt {...props}/>
  const install = () => void repair({ key: 'transcription', ...(check || { ok: false, code: 'whisper_not_installed' }), repair: 'install_whisper' } as ReadinessIssue)
  return <div className="studio-readiness" role="alertdialog" aria-label={t('需要先安装本地转写')}>
    <b>{t('需要先安装本地转写')}</b>
    <span>{t('视频没有字幕，所选的本地 Whisper 还没装好。安装完成后再开始，或改用云端转写。')}</span>
    <div className="studio-actions">
      <Btn size="sm" disabled={busy || repairing} loading={repairing} onClick={install}>{t('一键安装')}</Btn>
      <Btn size="sm" disabled={busy || repairing} onClick={() => navigate(CLOUD_TRANSCRIPTION_DESTINATION)}>{t('改用云端转写')}</Btn>
    </div>
  </div>
}
