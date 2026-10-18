import catalog from '@event-catalog'
import messages from '@failure-messages'

export const STUDIO_ERROR_CODES: readonly string[] = catalog.enums.studio_error_code
export const USER_CAUSE_ERROR_CODES: readonly string[] = catalog.attribution.user_cause.error_codes
export const USER_CAUSE_UPSTREAM_TYPES: readonly string[] = catalog.attribution.user_cause.upstream_types
export const USER_MESSAGES: Record<string, string> = messages
export const ERROR_CODE = new RegExp(`^(?:http_[45][0-9]{2}|${STUDIO_ERROR_CODES.join('|')})$`)
