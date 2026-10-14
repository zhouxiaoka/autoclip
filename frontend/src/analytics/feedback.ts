/**
 * 应用内反馈（PostHog Surveys）。
 *
 * 目标：用户不用离开应用、不用注册 GitHub，就能把"哪里不对 / 想要什么"发出来，
 * 且自动带上排查所需的上下文（版本 / 系统 / 架构 / LLM provider & 模型 / 失败阶段与错误）。
 *
 * 实现要点：
 * - 业务事件只走 `captureBusinessEvent`（白名单信封 + opt-out）。
 * - `feedback_submitted` 只报枚举与匿名上下文，不含 `text` / `contact`。
 * - 用户正文只出现在用户自己打开的 GitHub 回退页。
 * - 若 PostHog 项目里存在名为 FEEDBACK_SURVEY_NAME（或 env 指定 id）的 Survey，
 *   同时按约定发 `survey shown` / `survey dismissed`，也走白名单。
 */
import { captureBusinessEvent, isAnalyticsEnabled, posthog } from './posthog'
import { settingsApi } from '../services/api'
import { modelSettingsApi } from '../features/settings/modelSettingsApi'
import { getRuntimeInfo } from './lifecycle'
import {
  buildFeedbackDraft,
  captureProperties,
  githubFallbackUrl,
  newFeedbackId,
  type FeedbackCategory,
  type FeedbackDraft,
} from './feedbackDraft'

export const FEEDBACK_SURVEY_NAME = 'AutoClip 应用内反馈'
export const FEEDBACK_ISSUES_URL = 'https://github.com/zhouxiaoka/autoclip/issues/new/choose'
export const FEEDBACK_DISCUSSIONS_URL = 'https://github.com/zhouxiaoka/autoclip/discussions'

const SURVEY_ID_ENV = import.meta.env.VITE_PUBLIC_POSTHOG_FEEDBACK_SURVEY_ID as string | undefined

export type { FeedbackCategory }
export type FeedbackSource = 'settings' | 'failure' | 'detail'

export interface FeedbackContext {
  source: FeedbackSource
  /** 失败态携带 */
  stage?: string
  error_message?: string
  error_code?: string
  project_id?: string
  /** 设置页 / 失败态都会尽量补齐 */
  llm_provider?: string
  llm_model?: string
  llm_base_url?: string
  transcription_provider?: string
  transcription_model?: string
}

interface SurveyLike {
  id: string
  name: string
  type?: string
  questions?: Array<{ id?: string; type?: string; question?: string }>
}

let cachedSurvey: SurveyLike | null | undefined

/** 找到用于收反馈的 Survey；找不到返回 null（不影响 feedback_submitted 的上报）。 */
export function resolveFeedbackSurvey(): Promise<SurveyLike | null> {
  if (cachedSurvey !== undefined) return Promise.resolve(cachedSurvey)
  return new Promise((resolve) => {
    if (typeof posthog?.getSurveys !== 'function' || !isAnalyticsEnabled()) {
      cachedSurvey = null
      return resolve(null)
    }
    try {
      posthog.getSurveys((surveys: unknown) => {
        const list = (Array.isArray(surveys) ? surveys : []) as SurveyLike[]
        const found =
          list.find((s) => SURVEY_ID_ENV && s.id === SURVEY_ID_ENV) ||
          list.find((s) => s.name === FEEDBACK_SURVEY_NAME) ||
          null
        cachedSurvey = found
        resolve(found)
      }, false)
    } catch {
      cachedSurvey = null
      resolve(null)
    }
  })
}

/** 读取当前 LLM provider / 模型，补进反馈上下文；后端不可达时静默忽略。 */
export async function collectLlmContext(): Promise<Pick<FeedbackContext, 'llm_provider' | 'llm_model' | 'llm_base_url' | 'transcription_provider' | 'transcription_model'>> {
  const [provider, models] = await Promise.allSettled([settingsApi.getCurrentProvider(), modelSettingsApi.get()])
  const p = provider.status === 'fulfilled' ? provider.value : null
  const transcription = models.status === 'fulfilled' ? models.value.transcription : null
  return {
      llm_provider: p?.provider,
      llm_model: p?.model,
      llm_base_url: p?.base_url || undefined,
      transcription_provider: transcription?.provider,
      transcription_model: transcription?.model,
  }
}

export function trackFeedbackOpened(ctx: FeedbackContext, survey: SurveyLike | null): void {
  captureBusinessEvent('feedback_opened', { source: ctx.source, stage: ctx.stage })
  if (survey) captureBusinessEvent('survey shown', { $survey_id: survey.id, $survey_name: survey.name })
}

export function trackFeedbackDismissed(ctx: FeedbackContext, survey: SurveyLike | null): void {
  captureBusinessEvent('feedback_dismissed', { source: ctx.source })
  if (survey) captureBusinessEvent('survey dismissed', { $survey_id: survey.id, $survey_name: survey.name })
}

export interface FeedbackPayload {
  category: FeedbackCategory
  text: string
  contact?: string
  context: FeedbackContext
}

export interface FeedbackDelivery {
  ok: boolean
  fallbackUrl: string
}

/**
 * 分析开着时记一条不含正文的 `feedback_submitted`。
 * 用户正文只放进 GitHub 回退链接；关闭分析或未初始化时不发 PostHog。
 */
export async function submitFeedback(payload: FeedbackPayload): Promise<FeedbackDelivery> {
  const runtime = getRuntimeInfo()
  const draft: FeedbackDraft = buildFeedbackDraft({
    feedbackId: newFeedbackId(),
    category: payload.category,
    text: payload.text,
    contact: payload.contact,
    source: payload.context.source,
    stage: payload.context.stage,
    errorMessage: payload.context.error_message,
    errorCode: payload.context.error_code,
    version: runtime.version,
    os: runtime.os,
    arch: runtime.arch,
    llmProvider: payload.context.llm_provider,
    llmModel: payload.context.llm_model,
    transcriptionProvider: payload.context.transcription_provider,
    transcriptionModel: payload.context.transcription_model,
  })
  const fallbackUrl = githubFallbackUrl(draft)
  const captured = captureBusinessEvent('feedback_submitted', captureProperties(draft))
  return { ok: captured, fallbackUrl }
}
