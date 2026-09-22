/**
 * 应用内反馈（PostHog Surveys）。
 *
 * 目标：用户不用离开应用、不用注册 GitHub，就能把"哪里不对 / 想要什么"发出来，
 * 且自动带上排查所需的上下文（版本 / 系统 / 架构 / LLM provider & 模型 / 失败阶段与错误）。
 *
 * 实现要点：
 * - 反馈以 `feedback_submitted` 事件进入 PostHog（无论有没有配置 Survey 都会发）。
 * - 若 PostHog 项目里存在名为 FEEDBACK_SURVEY_NAME（或 env 指定 id）的 Survey（API 型 / 无 UI），
 *   同时按 PostHog 的约定发 `survey shown` / `survey sent` / `survey dismissed`，
 *   这样结果会出现在 PostHog → Surveys 的响应面板里，周报也能直接读。
 * - 版本 / 系统 / 架构 由 lifecycle.ts 注册的 super properties 自动携带；这里额外显式写入，
 *   避免 Surveys 面板只看 `$survey_response*` 时丢上下文。
 * - 点「发送」不看匿名统计开关。事件进入 PostHog 后，收件任务写进 GitHub。
 *   故障开 Issue，想法开 Ideas，其他开 Q&A。邮箱不进公开帖。
 * - 没有配置或网络失败时，打开预填好的 GitHub 页面，由用户再提交一次。
 */
import { posthog, isAnalyticsEnabled, POSTHOG_HOST, POSTHOG_KEY } from './posthog'
import { settingsApi } from '../services/api'
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
  project_id?: string
  /** 设置页 / 失败态都会尽量补齐 */
  llm_provider?: string
  llm_model?: string
  llm_base_url?: string
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
export async function collectLlmContext(): Promise<Pick<FeedbackContext, 'llm_provider' | 'llm_model' | 'llm_base_url'>> {
  try {
    const p = await settingsApi.getCurrentProvider()
    return {
      llm_provider: p?.provider,
      llm_model: p?.model,
      llm_base_url: p?.base_url || undefined,
    }
  } catch {
    return {}
  }
}

export function trackFeedbackOpened(ctx: FeedbackContext, survey: SurveyLike | null): void {
  if (typeof posthog?.capture !== 'function') return
  posthog.capture('feedback_opened', { source: ctx.source, stage: ctx.stage })
  if (survey) posthog.capture('survey shown', { $survey_id: survey.id, $survey_name: survey.name })
}

export function trackFeedbackDismissed(ctx: FeedbackContext, survey: SurveyLike | null): void {
  if (typeof posthog?.capture !== 'function') return
  posthog.capture('feedback_dismissed', { source: ctx.source })
  if (survey) posthog.capture('survey dismissed', { $survey_id: survey.id, $survey_name: survey.name })
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

function feedbackDistinctId(draft: FeedbackDraft): string {
  if (isAnalyticsEnabled()) {
    try {
      const current = posthog.get_distinct_id?.()
      if (current) return current
    } catch { /* 显式反馈仍要发出 */ }
  }
  return `feedback:${draft.feedbackId}`
}

/**
 * 主动发送不看匿名统计开关。成功时事件进入 PostHog，随后由收件任务写进 GitHub。
 * 没有配置或网络失败时，返回预填好的 GitHub 链接，由调用方打开。
 */
export async function submitFeedback(payload: FeedbackPayload): Promise<FeedbackDelivery> {
  const runtime = getRuntimeInfo()
  const draft = buildFeedbackDraft({
    feedbackId: newFeedbackId(),
    category: payload.category,
    text: payload.text,
    contact: payload.contact,
    source: payload.context.source,
    stage: payload.context.stage,
    errorMessage: payload.context.error_message,
    version: runtime.version,
    os: runtime.os,
    arch: runtime.arch,
    llmProvider: payload.context.llm_provider,
    llmModel: payload.context.llm_model,
  })
  const fallbackUrl = githubFallbackUrl(draft)
  if (!POSTHOG_KEY) return { ok: false, fallbackUrl }
  try {
    const response = await fetch(`${POSTHOG_HOST.replace(/\/$/, '')}/capture/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'omit',
      body: JSON.stringify({
        api_key: POSTHOG_KEY,
        event: 'feedback_submitted',
        distinct_id: feedbackDistinctId(draft),
        timestamp: new Date().toISOString(),
        properties: captureProperties(draft),
      }),
      signal: typeof AbortSignal.timeout === 'function' ? AbortSignal.timeout(8000) : undefined,
    })
    return { ok: response.ok, fallbackUrl }
  } catch {
    return { ok: false, fallbackUrl }
  }
}
