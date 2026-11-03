/** Smart projects hide the old confirm / collection / export-confirm path. Classic projects keep it. */

export const LEGACY_ACTIONS = ['start_processing', 'collection', 'export_confirm', 'plan_adjust', 'preferences'] as const
export type LegacyAction = (typeof LEGACY_ACTIONS)[number]

export function legacyEntrypointsHidden(enabled: boolean, smartProject: boolean): boolean {
  return enabled && smartProject
}
