type TFn = (key: string) => string

/** zh source string doubles as the i18n key (8 locales). */
const WHISPER_DOWNLOAD_FAILED = 'Whisper 模型下载失败。请检查网络后到「设置 → 默认模型 → 语音转字幕」重新下载，或在下载源中改用 hf-mirror 镜像。'

/** pick translated copy by the stable backend errorCode; legacy rows keep errorMessage.*/
export function whisperModelErrorText(t: TFn, model: { errorCode?: string | null; errorMessage?: string | null }): string {
  if (model.errorCode === 'whisper_download_failed') return t(WHISPER_DOWNLOAD_FAILED)
  return model.errorMessage || ''
}
