import { t } from '../../i18n'
import { Btn } from '../../ui'
import { CLOUD_TRANSCRIPTION_DESTINATION, repairDestination } from './importReadiness'
import type { RecoveryState } from './transcriptionRecovery'

export interface TranscriptionGatePromptProps {
  state: RecoveryState
  busy: boolean
  /** One-click install (runtime -> model) through the shared recovery controller. */
  onInstall: () => void | Promise<void>
  /** Failed or timed out: same path as install. */
  onRetry: () => void | Promise<void>
  /** Ready: start the same import / confirmation again. */
  onContinue: () => void
  navigate: (to: string) => void
}

/** The one view of the install-recovery controller (#418 rewrite), used by the import page and the confirm page.
 * Every phase has an exit: install, wait with progress, continue, or retry / transcription settings. */
export default function TranscriptionGatePrompt({ state, busy, onInstall, onRetry, onContinue, navigate }: TranscriptionGatePromptProps) {
  const settings = () => navigate(repairDestination('settings_transcription') as string)
  // #371: a background install stays inline while it runs; #404: once it failed or timed out it is shown, with retry.
  const ended = state.phase === 'failed' || state.phase === 'timeout'
  if (state.phase === 'idle' || (state.background && !ended)) return null
  if (state.phase === 'install_required') return <div className="studio-readiness" role="alertdialog" aria-label={t('需要先安装本地转写')}>
    <b>{t('需要先安装本地转写')}</b>
    <span>{t('视频没有字幕，需要本地转写组件（约 220 MB，国内约 15 分钟），或改用云端转写。')}</span>
    <div className="studio-actions">
      <Btn size="sm" disabled={busy} onClick={() => void onInstall()}>{t('一键安装')}</Btn>
      <Btn size="sm" disabled={busy} onClick={() => navigate(CLOUD_TRANSCRIPTION_DESTINATION)}>{t('改用云端转写')}</Btn>
    </div>
  </div>
  return <div className="studio-readiness" role="alertdialog" aria-label={t('等待安装完成')}>
    <b>{t('等待安装完成')}</b>
    {state.phase === 'ready' ? <>
      <span>{t('本地转写已就绪，可以继续导入。')}</span>
      <div className="studio-actions"><Btn size="sm" disabled={busy} onClick={onContinue}>{t('继续导入')}</Btn></div>
    </> : state.phase === 'failed' || state.phase === 'timeout' ? <>
      <span className="studio-error">{t(state.phase === 'timeout' ? '安装长时间没有进展，可以重试，或到转写设置里查看。'
        : state.offline ? '暂时连不上本地后端。后端恢复后会自动继续，也可以重试。' : '安装或模型下载失败，可以重试，或到转写设置里查看。')}</span>
      <div className="studio-actions">
        <Btn size="sm" disabled={busy} onClick={() => void onRetry()}>{t('重试')}</Btn>
        <Btn size="sm" disabled={busy} onClick={settings}>{t('打开转写设置')}</Btn>
      </div>
    </> : <>
      <span>{t(state.phase === 'downloading' ? '正在下载转写模型，下载完成后即可继续。' : '本地 Whisper 正在安装，装好后再开始。')}</span>
      <span className="studio-muted">{t(state.phase === 'downloading'
        ? '没有字幕的视频，第一次要下载本地转写组件（约 220 MB，国内网络约 15 分钟）。'
        : '没有字幕的视频，第一次要下载本地转写组件（约 220 MB，国内网络约 15 分钟）。不想等可以改用云端转写。')}</span>
      {state.unreachable && <span className="studio-muted">{t('暂时连不上本地后端，正在重试…')}</span>}
      {state.percent != null && <span className="studio-muted" role="progressbar" aria-valuenow={state.percent} aria-valuemin={0} aria-valuemax={100}>{t('已完成 {{percent}}%', { percent: state.percent })}</span>}
      <div className="studio-actions"><Btn size="sm" onClick={settings}>{t('打开转写设置')}</Btn></div>
    </>}
  </div>
}
