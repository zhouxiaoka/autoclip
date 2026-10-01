import { t } from '../../i18n'

export const REPO_URL = 'https://github.com/zhouxiaoka/autoclip'
export const USE_CASE_URL = `${REPO_URL}/discussions/new?category=use-cases`
const RATING_KEY = 'autoclip.output-rating.v1'
const RATING_INTERVAL_MS = 7 * 86400000

/** Caption the user pastes next to the posted video. Nothing is uploaded by AutoClip. */
export function shareCaption(title: string | undefined, english = false): string {
  // The credit is pasted with the post, so it follows the platform's language, not the app's.
  const credit = `${english ? 'Made with AutoClip' : t('用 AutoClip 剪的')} · ${REPO_URL}`
  return title?.trim() ? `${title.trim()}\n\n${credit}` : credit
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    const area = document.createElement('textarea')
    area.value = text
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    const copied = document.execCommand('copy')
    area.remove()
    return copied
  }
}

type RatingState = { askedAt?: number; projects?: string[] }

function readRating(storage: Storage): RatingState {
  try { return JSON.parse(storage.getItem(RATING_KEY) || '{}') as RatingState } catch { return {} }
}

/** Ask at most once per project and at most once a week overall. Project ids stay in local storage only. */
export function shouldAskRating(projectKey: string, now = Date.now(), storage: Storage = localStorage): boolean {
  const state = readRating(storage)
  if (state.projects?.includes(projectKey)) return false
  return !state.askedAt || now - state.askedAt >= RATING_INTERVAL_MS
}

export function markRatingAsked(projectKey: string, now = Date.now(), storage: Storage = localStorage) {
  const state = readRating(storage)
  const projects = [...(state.projects || []).filter(item => item !== projectKey), projectKey].slice(-50)
  storage.setItem(RATING_KEY, JSON.stringify({ askedAt: now, projects }))
}
