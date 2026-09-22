/**
 * 应用内反馈的公开草稿。
 * 邮箱只留给维护者的收件记录，不进入 GitHub 的标题、正文或预填链接。
 */
export type FeedbackCategory = 'bug' | 'idea' | 'other'

export interface FeedbackDraftInput {
  feedbackId: string
  category: FeedbackCategory
  text: string
  contact?: string
  source: string
  stage?: string
  errorMessage?: string
  version: string
  os: string
  arch: string
  llmProvider?: string
  llmModel?: string
}

export interface FeedbackDraft {
  feedbackId: string
  category: FeedbackCategory
  text: string
  contact?: string
  source: string
  stage?: string
  errorMessage?: string
  version: string
  os: string
  arch: string
  llmProvider?: string
  llmModel?: string
  title: string
}

const SECRET = /sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{8,}|github_pat_[A-Za-z0-9_]{8,}|xox[baprs]-[A-Za-z0-9-]+|(?:api[_-]?key|token|secret|password|bearer)\s*[:=]\s*\S+/gi

export function newFeedbackId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (ch) => {
    const rand = Math.floor(Math.random() * 16)
    const value = ch === 'x' ? rand : (rand & 0x3) | 0x8
    return value.toString(16)
  })
}

export function scrubText(value: string | undefined, max = 2000): string {
  return (value || '').replace(SECRET, '[redacted]').replace(/\r\n/g, '\n').trim().slice(0, max)
}

export function buildFeedbackDraft(input: FeedbackDraftInput): FeedbackDraft {
  const text = scrubText(input.text, 2000)
  const category = input.category
  const prefix = category === 'idea' ? '[想法] ' : '[反馈] '
  const line = text.split('\n')[0].replace(/\s+/g, ' ').trim()
  const title = (prefix + (line || '应用内反馈')).slice(0, 120)
  const contact = scrubText(input.contact, 200)
  return {
    feedbackId: input.feedbackId,
    category,
    text,
    contact: contact || undefined,
    source: scrubText(input.source, 40),
    stage: scrubText(input.stage, 80) || undefined,
    errorMessage: scrubText(input.errorMessage, 500) || undefined,
    version: scrubText(input.version, 40),
    os: scrubText(input.os, 40),
    arch: scrubText(input.arch, 40),
    llmProvider: scrubText(input.llmProvider, 80) || undefined,
    llmModel: scrubText(input.llmModel, 80) || undefined,
    title,
  }
}

/** 发给 PostHog 的字段。不含接口地址。邮箱只出现在这里。 */
export function captureProperties(draft: FeedbackDraft): Record<string, string> {
  const props: Record<string, string> = {
    feedback_id: draft.feedbackId,
    category: draft.category,
    text: draft.text,
    source: draft.source,
    app_version: draft.version,
    os: draft.os,
    arch: draft.arch,
    $lib: 'autoclip-feedback',
  }
  if (draft.contact) props.contact = draft.contact
  if (draft.stage) props.stage = draft.stage
  if (draft.errorMessage) props.error_message = draft.errorMessage
  if (draft.llmProvider) props.llm_provider = draft.llmProvider
  if (draft.llmModel) props.llm_model = draft.llmModel
  return props
}

function platformLabel(os: string): string {
  if (os === 'macos') return 'macOS 桌面版 (Apple Silicon)'
  if (os === 'windows') return 'Windows 桌面版 (x64)'
  if (os === 'linux') return 'Docker'
  return '源码运行 / From source'
}

function publicLines(draft: FeedbackDraft): string {
  const lines = [
    draft.text,
    '',
    `反馈编号：${draft.feedbackId}`,
    `<!-- feedback-id:${draft.feedbackId} -->`,
    '',
    `版本：${draft.version || '未知'}`,
    `系统：${draft.os || '未知'} / ${draft.arch || '未知'}`,
    `来源：${draft.source || '未知'}`,
  ]
  if (draft.stage) lines.push(`阶段：${draft.stage}`)
  if (draft.llmProvider) lines.push(`模型：${draft.llmProvider}${draft.llmModel ? ` / ${draft.llmModel}` : ''}`)
  if (draft.errorMessage) lines.push('', '错误', draft.errorMessage)
  return lines.join('\n').slice(0, 1500)
}

/** 直接送达失败时打开的预填页。链接里没有邮箱。 */
export function githubFallbackUrl(draft: FeedbackDraft): string {
  if (draft.category === 'bug') {
    const params = new URLSearchParams({
      template: 'bug_report.yml',
      title: draft.title,
      version: draft.version || 'unknown',
      model: draft.llmProvider ? `${draft.llmProvider}${draft.llmModel ? ` / ${draft.llmModel}` : ''}` : '未知',
      platform: platformLabel(draft.os),
      source: '不相关 / N/A',
      what: publicLines(draft),
    })
    return `https://github.com/zhouxiaoka/autoclip/issues/new?${params}`
  }
  const params = new URLSearchParams({
    category: draft.category === 'idea' ? 'ideas' : 'q-a',
    title: draft.title,
    body: publicLines(draft),
  })
  return `https://github.com/zhouxiaoka/autoclip/discussions/new?${params}`
}
