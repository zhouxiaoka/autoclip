/**
 * 关键业务事件（见 ROADMAP.md Phase 0：导入 / 出片 / 失败 / 设置 key）。
 *
 * 统一在这里定义事件名与载荷类型，避免裸字符串散落各处。
 * 所有 capture 都通过 trackEvent，未初始化 / 已关闭时自动 no-op。
 */
import { captureBusinessEvent } from './posthog'

export const AnalyticsEvent = {
  /** 导入素材（上传/选择视频开始一个项目） */
  VideoImported: 'video_imported',
  /** Legacy: one downloadVideo call received a file and triggered browser download. */
  ClipsExported: 'clips_exported',
  /** 关键流程失败（导入/转写/切片/导出任一环节） */
  ProcessingFailed: 'processing_failed',
  /** 设置/更新 LLM API key */
  ApiKeyConfigured: 'api_key_configured',
} as const

export type AnalyticsEventName =
  (typeof AnalyticsEvent)[keyof typeof AnalyticsEvent]

/** 通用埋点入口。posthog 未初始化或已 opt-out 时为 no-op（内部已处理）。 */
function trackEvent(
  name: AnalyticsEventName,
  properties?: Record<string, string | number | boolean | undefined>,
): void {
  captureBusinessEvent(name, properties)
}

export function trackVideoImported(props?: {
  source?: 'upload' | 'url' | 'local'
  fileType?: string
  durationSec?: number
  sizeBytes?: number
}): void {
  trackEvent(AnalyticsEvent.VideoImported, props)
}

export function trackClipsExported(props?: {
  clipCount?: number
  durationSec?: number
  withSubtitles?: boolean
  exportType?: 'clip' | 'collection' | 'project'
}): void {
  trackEvent(AnalyticsEvent.ClipsExported, props)
}

export function trackProcessingFailed(props: {
  stage: 'import' | 'transcribe' | 'analyze' | 'clip' | 'export' | 'other'
  message?: string
  code?: string | number
}): void {
  // Never send arbitrary exception text (may contain tokens, URLs or local paths).
  trackEvent(AnalyticsEvent.ProcessingFailed, { stage: props.stage, code: props.code })
}

export function trackApiKeyConfigured(props: {
  provider: string
  /** 不要传 key 明文，仅标记是否填写 */
  hasKey: boolean
}): void {
  trackEvent(AnalyticsEvent.ApiKeyConfigured, props)
}
