/**
 * First-run chooser: 88API (default), Infistar, or jump to the full settings page.
 * Deeplink write is out of scope; one-click only opens the sponsor registration URL.
 */
export const FIRST_RUN_CHOICES = ['api88', 'infistar', 'other'] as const
export type FirstRunChoice = (typeof FIRST_RUN_CHOICES)[number]
export type FirstRunAction = 'later' | 'open_settings' | 'one_click'

export const FIRST_RUN_DEFAULT: FirstRunChoice = 'api88'

export function firstRunPrimaryAction(choice: FirstRunChoice): Exclude<FirstRunAction, 'later'> {
  return choice === 'other' ? 'open_settings' : 'one_click'
}

export function firstRunSponsor(choice: FirstRunChoice): 'api88' | 'infistar' | null {
  return choice === 'other' ? null : choice
}

export function firstRunPrimaryLabel(choice: FirstRunChoice, sponsorName = ''): { key: string; values?: { name: string } } {
  if (choice === 'other') return { key: '去设置选择其他服务商' }
  return { key: '通过 {{name}} 一键获取', values: { name: sponsorName } }
}
