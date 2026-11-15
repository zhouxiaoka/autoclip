/**
 * First-run chooser: APIMart (default), 88API, or a measured default under 「其他」.
 * Infistar stays a saved-provider preset; it is not offered here.
 * Deeplink write is out of scope; one-click only opens the sponsor registration URL.
 * 「其他」 connects DeepSeek, or on zh the higher tier of DeepSeek and DashScope.
 */
import { firstRunOtherDefault, pickHigherQuality } from './providerQuality'

export const FIRST_RUN_CHOICES = ['apimart', 'api88', 'other'] as const
export type FirstRunChoice = (typeof FIRST_RUN_CHOICES)[number]
export type FirstRunAction = 'later' | 'open_settings' | 'one_click' | 'connect_recommended'

export const FIRST_RUN_DEFAULT: FirstRunChoice = 'apimart'

export { firstRunOtherDefault, pickHigherQuality }

export function firstRunPrimaryAction(choice: string): Exclude<FirstRunAction, 'later'> {
  return choice === 'other' ? 'connect_recommended' : 'one_click'
}

export function firstRunSponsor(choice: string): 'apimart' | 'api88' | null {
  if (choice === 'apimart' || choice === 'api88') return choice
  return null
}

export function firstRunPrimaryLabel(choice: string, sponsorName = ''): { key: string; values?: { name: string } } {
  if (choice === 'other') return { key: '连接 {{name}}', values: { name: sponsorName } }
  return { key: '通过 {{name}} 一键获取', values: { name: sponsorName } }
}
