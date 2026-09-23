import { t } from '../i18n'
import React from 'react'
import { Btn } from '../ui'
import { SubtitleFailureKind } from '../utils/subtitleFailure'

function copyFor(kind: SubtitleFailureKind): { title: string; body: string } {
  switch (kind) {
    case 'whisper_not_installed':
      return {
        title: t("还没有安装本地转写"),
        body: t("这条视频没有自带字幕。到「设置 → 转写」安装 Whisper 并下载一个模型，或重新导入时带上 .srt。"),
      }
    case 'whisper_install_failed':
      return {
        title: t("Whisper 上次没有装上"),
        body: t("这条视频没有自带字幕，而且上次安装 Whisper 没有成功。到「设置 → 转写」重试安装，或重新导入时带上 .srt。"),
      }
    case 'transcription_empty':
      return {
        title: t("转写没有得到字幕"),
        body: t("Whisper 已经装好，但这条视频没有识别出可用语音。确认有清晰人声后重试，或重新导入时带上 .srt。"),
      }
    case 'subtitle_unknown':
      return {
        title: t("没有字幕可分析"),
        body: t("这条视频没有自带字幕，本地转写也没有结果。可以到「设置 → 转写」安装或重试 Whisper，也可以重新导入时带上 .srt。"),
      }
    default:
      return {
        title: t("这次处理没有成功"),
        body: t("到「设置 → 转写」检查 Whisper 是否安装、模型是否已下载，或重新导入时带上 .srt。"),
      }
  }
}

/** 失败空态：一句原因、一句可做的事、打开「设置 → 转写」的主按钮。 */
const SubtitleFailureEmpty: React.FC<{
  kind: SubtitleFailureKind
  errorMessage?: string
  onOpenSettings: () => void
}> = ({ kind, errorMessage, onOpenSettings }) => {
  const copy = copyFor(kind)
  return (
    <div className="ac-empty" style={{ marginTop: 32 }}>
      <b>{copy.title}</b>
      <span style={{ display: 'block', maxWidth: 520, margin: '6px auto 0', lineHeight: 1.5 }}>{copy.body}</span>
      {errorMessage && (
        <span className="ac-mono" style={{ display: 'block', marginTop: 10, color: 'var(--ac-muted)', wordBreak: 'break-word' }}>
          {errorMessage}
        </span>
      )}
      <div style={{ marginTop: 16 }}>
        <Btn variant="cta" size="sm" onClick={onOpenSettings}>{t("打开转写设置")}</Btn>
      </div>
    </div>
  )
}

export default SubtitleFailureEmpty
