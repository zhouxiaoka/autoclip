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
 * - 埋点被用户关闭时，PostHog 侧不会发出；此时回退到官网飞书表单（FEEDBACK_FORM_URL）。
 */
import { posthog, isAnalyticsEnabled } from './posthog'
import { settingsApi } from '../services/api'

export const FEEDBACK_SURVEY_NAME = 'AutoClip 应用内反馈'
export const FEEDBACK_FORM_URL = 'https://my.feishu.cn/share/base/shrcn8hKUG2icIJLpNry6uWVNJe'
export const FEEDBACK_ISSUES_URL = 'https://github.com/zhouxiaoka/autoclip/issues/new/choose'

const SURVEY_ID_ENV = import.meta.env.VITE_PUBLIC_POSTHOG_FEEDBACK_SURVEY_ID as string | undefined

export type FeedbackCategory = 'bug' | 'idea' | 'other'
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

/**
 * 提交反馈。返回 true 表示已通过 PostHog 发出；false 表示埋点关闭 / 未初始化，
 * 调用方应引导用户改用飞书表单。
 */
export async function submitFeedback(payload: FeedbackPayload): Promise<boolean> {
  if (typeof posthog?.capture !== 'function' || !isAnalyticsEnabled()) return false

  const survey = await resolveFeedbackSurvey()
  const props: Record<string, unknown> = {
    category: payload.category,
    text: payload.text,
    contact: payload.contact || undefined,
    ...payload.context,
  }
  posthog.capture('feedback_submitted', props)

  if (survey) {
    const qs = survey.questions || []
    const responses: Record<string, unknown> = {
      $survey_id: survey.id,
      $survey_name: survey.name,
      $survey_questions: qs.map((q) => ({ id: q.id, question: q.question })),
      // 第一题：自由文本
      $survey_response: payload.text,
      ...props,
    }
    // 兼容 question-id 键：第一题 = 文本，后续 single_choice 题 = 分类
    qs.forEach((q, i) => {
      const key = q.id ? `$survey_response_${q.id}` : `$survey_response_${i}`
      if (i === 0) responses[key] = payload.text
      else if (q.type === 'single_choice' || q.type === 'multiple_choice') responses[key] = payload.category
      else if (/联系|contact|email/i.test(q.question || '')) responses[key] = payload.contact || ''
    })
    posthog.capture('survey sent', responses)
  }
  return true
}
