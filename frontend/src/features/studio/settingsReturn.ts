/**
 * 「去设置」 from a failed project remembers the project; once the model settings are saved
 * successfully (and pass validation) the app returns to that project, where the failed step shows
 * 「继续制作」 (the same retry API: new attempt_id + retry_of).
 */
export const SETTINGS_SAVED_EVENT = 'autoclip:model-settings-saved'
const RETURN_PARAM = 'return_project'
export const CONTINUE_PARAM = 'continue'

export function settingsReturnUrl(destination: string, projectId: string): string {
  return `${destination}${destination.includes('?') ? '&' : '?'}${RETURN_PARAM}=${encodeURIComponent(projectId)}`
}

/** Where to go after a successful save on `search` (the settings page query), or null to stay. */
export function returnAfterSave(search: string): string | null {
  const pid = new URLSearchParams(search).get(RETURN_PARAM)
  return pid && /^[\w-]{1,128}$/.test(pid) ? `/project/${encodeURIComponent(pid)}?${CONTINUE_PARAM}=1` : null
}

/** The only save notification. A notification problem never turns a saved settings into a failure.*/
export function notifySettingsSaved(target: { dispatchEvent(e: Event): boolean } | undefined = typeof window === 'undefined' ? undefined : window) {
  try { target?.dispatchEvent(new Event(SETTINGS_SAVED_EVENT)) } catch { /* no DOM (tests / SSR) */ }
}
