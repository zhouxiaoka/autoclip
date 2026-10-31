/**
 * First-run chooser: 88API (default), Infistar, or a measured default under 「其他」.
 * Deeplink write is out of scope; one-click only opens the sponsor registration URL.
 * 「其他」 connects DeepSeek, or on zh the higher tier of DeepSeek and DashScope.
 */
import { firstRunOtherDefault, pickHigherQuality } from './providerQuality'

export const FIRST_RUN_CHOICES = ['api88', 'infistar', 'other'] as const
export type FirstRunChoice = (typeof FIRST_RUN_CHOICES)[number]
export type FirstRunAction = 'later' | 'open_settings' | 'one_click' | 'connect_recommended'

export const FIRST_RUN_DEFAULT: FirstRunChoice = 'api88'

export { firstRunOtherDefault, pickHigherQuality }

export function firstRunPrimaryAction(choice: FirstRunChoice): Exclude<FirstRunAction, 'later'> {
  return choice === 'other' ? 'connect_recommended' : 'one_click'
}

export function firstRunSponsor(choice: FirstRunChoice): 'api88' | 'infistar' | null {
  return choice === 'other' ? null : choice
}

export function firstRunPrimaryLabel(choice: FirstRunChoice, sponsorName = ''): { key: string; values?: { name: string } } {
  if (choice === 'other') return { key: '连接 {{name}}', values: { name: sponsorName } }
  return { key: '通过 {{name}} 一键获取', values: { name: sponsorName } }
}
