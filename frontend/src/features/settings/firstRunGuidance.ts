/**
 * Packaged first-run chooser: APIMart (default) or a measured default under 「其他」.
 * 88API and Infistar are not in that packaged list. An accepted signed view may
 * still name either id, because the register host is already trusted.
 * Deeplink write is out of scope; one-click only opens a currently eligible register URL.
 * 「其他」 connects DeepSeek, or on zh the higher tier of DeepSeek and DashScope.
 */
import { firstRunOtherDefault, pickHigherQuality } from './providerQuality'
import { isTrustedSponsorId } from './sponsorPromoState'

export const FIRST_RUN_CHOICES = ['apimart', 'other'] as const
export type FirstRunChoice = (typeof FIRST_RUN_CHOICES)[number]
export type FirstRunAction = 'later' | 'open_settings' | 'one_click' | 'connect_recommended'

export const FIRST_RUN_DEFAULT: FirstRunChoice = 'apimart'

export { firstRunOtherDefault, pickHigherQuality }

export function firstRunPrimaryAction(choice: string): Exclude<FirstRunAction, 'later'> {
  return choice === 'other' ? 'connect_recommended' : 'one_click'
}

export function firstRunSponsor(choice: string): string | null {
  return isTrustedSponsorId(choice) ? choice : null
}

export function firstRunPrimaryLabel(choice: string, sponsorName = ''): { key: string; values?: { name: string } } {
  if (choice === 'other') return { key: '连接 {{name}}', values: { name: sponsorName } }
  return { key: '通过 {{name}} 一键获取', values: { name: sponsorName } }
}
