/**
 * 1.5.8 failed-state action. User-attributable causes (bad/expired key, no balance, no model
 * configured, key lacks permission) cannot be fixed by retrying: show 「去设置」 instead.
 * Mirrors event_catalog.json attribution.user_cause (contract-tested; same set the v4
 * success rate excludes as user cause).
 */
export const USER_CAUSE_ERROR_CODES = ['authentication', 'llm_auth_invalid', 'invalid_key', 'insufficient_quota', 'llm_not_configured'] as const
export const USER_CAUSE_UPSTREAM_TYPES = ['invalid_key', 'insufficient_quota', 'permission_denied'] as const

export const SETTINGS_DESTINATION = '/settings?section=analysis'
/** Cloud transcription (ASR) credentials. SettingsPage maps `speech` to the transcription row;
 * `section=transcription` is not a recognised value there (falls back to the top of AI settings). */
export const TRANSCRIPTION_SETTINGS_DESTINATION = '/settings?section=speech'

const REASONS: Record<string, string> = {
  authentication: 'API Key 无效或已过期，请到设置里更新后再试',
  llm_auth_invalid: 'API Key 无效或已过期，请到设置里更新后再试',
  invalid_key: 'API Key 无效或已过期，请到设置里更新后再试',
  insufficient_quota: '服务商账户余额不足，请充值或换一个服务商',
  permission_denied: '这个 API Key 没有该模型的使用权限，请到设置里更换',
  llm_not_configured: '还没有配置可用的模型，请先到设置里添加',
}

export type FailureAction = { kind: 'retry' } | { kind: 'settings'; reason: string; destination: string }

/** Which settings row fixes a user-cause failure, keyed by failure_stage (one table):
 * subtitle = cloud transcription (ASR), vision = visual-understanding binding; everything else
 * is the text-analysis binding. Values are SettingsPage SECTION_ALIASES keys. */
const STAGE_SECTION: Record<string, string> = { subtitle: 'speech', vision: 'vision' }
export const VISION_SETTINGS_DESTINATION = '/settings?section=vision'

export function settingsDestination(failureStage?: string | null): string {
  const section = STAGE_SECTION[failureStage || '']
  return section ? `/settings?section=${section}` : SETTINGS_DESTINATION
}

const isIn = (list: readonly string[], value?: string | null): value is string => !!value && list.includes(value)

/** One classification: the controlled upstream type is the most precise signal and wins; the
 * coarse error_code is only used when upstream says nothing user-attributable. */
export function failureAction(errorCode?: string | null, upstreamType?: string | null, failureStage?: string | null): FailureAction {
  const code = isIn(USER_CAUSE_UPSTREAM_TYPES, upstreamType) ? upstreamType
    : isIn(USER_CAUSE_ERROR_CODES, errorCode) || isIn(USER_CAUSE_UPSTREAM_TYPES, errorCode) ? errorCode : ''
  return code ? { kind: 'settings', reason: REASONS[code], destination: settingsDestination(failureStage) } : { kind: 'retry' }
}
