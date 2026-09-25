/** 没有字幕可分析：前端用来决定要不要打开「设置 → 转写」，以及换哪一句说明。 */
export type SubtitleFailureKind =
  | 'whisper_not_installed'
  | 'whisper_install_failed'
  | 'transcription_empty'
  | 'subtitle_setup'
  | 'subtitle_unknown'

const CODES = new Set<SubtitleFailureKind>([
  'whisper_not_installed',
  'whisper_install_failed',
  'transcription_empty',
  'subtitle_setup',
  'subtitle_unknown',
])

function mentionsSubtitle(text: string): boolean {
  return /字幕|转写|Whisper|whisper/.test(text)
}

/**
 * 有 error_code 时以它为准。旧版只存了一句「没有字幕可分析…本地转写没有生成结果」，
 * 那种情况返回 subtitle_unknown，详情页可以再问一次当前 Whisper 状态。
 */
export function classifySubtitleFailure(error?: string | null, code?: string | null): SubtitleFailureKind | null {
  if (code && CODES.has(code as SubtitleFailureKind)) return code as SubtitleFailureKind
  const text = error || ''
  if (!text || !mentionsSubtitle(text)) return null
  if (text.includes('上次安装没有成功') || text.includes('安装没有成功')) return 'whisper_install_failed'
  if (text.includes('还没安装') || text.includes('运行时未安装') || text.includes('没有可用的语音识别')) {
    return 'whisper_not_installed'
  }
  if (
    text.includes('没有生成可用字幕')
    || text.includes('未识别出任何语音')
    || text.includes('没有从这段视频')
  ) {
    return 'transcription_empty'
  }
  if (text.includes('本地转写没有生成结果')) return 'subtitle_unknown'
  if (text.includes('没有字幕可分析') || text.includes('设置 → 语音识别') || text.includes('设置 → 转写')) {
    return 'subtitle_setup'
  }
  // 导入关卡旧文案只有「字幕文件不存在」（#186）。没有 Whisper 状态，详情页再问一次当前安装情况。
  if (text.includes('字幕文件不存在')) return 'subtitle_unknown'
  return null
}
