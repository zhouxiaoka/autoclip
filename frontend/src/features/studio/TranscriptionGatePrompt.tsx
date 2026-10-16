import { t } from '../../i18n'
import { Btn } from '../../ui'
import { CLOUD_TRANSCRIPTION_DESTINATION, type ReadinessCheck, type ReadinessIssue } from './importReadiness'

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
}

/** 1.5.8 blocking prompt: install local Whisper, or open transcription settings. Never switches provider itself. */
export default function TranscriptionGatePrompt({ kind, check, busy, repairing, repair, navigate }: TranscriptionGatePromptProps) {
  if (kind === LOCAL_TRANSCRIPTION_INSTALLING) {
    return <div className="studio-readiness" role="alertdialog" aria-label={t('等待安装完成')}>
      <b>{t('等待安装完成')}</b>
      <span>{t('本地 Whisper 正在安装，装好后再开始。')}</span>
    </div>
  }
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
